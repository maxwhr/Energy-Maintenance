from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.services.knowledge_graph_fact_identity_service import KnowledgeGraphFactIdentityService
from app.services.kg_current_evidence_equivalence_service import KGCurrentEvidenceEquivalenceService
from app.services.kg_relation_evidence_type_matrix import KGRelationEvidenceTypeMatrix
from app.services.source_grounding_validator import SourceGroundingValidator
from app.services.task25g_r2_hashing import stable_hash


SUPPORT_PRIORITY = {
    "DIRECT_EXACT_SUPPORT": 8,
    "DIRECT_MULTI_SOURCE_SUPPORT": 7,
    "PARTIAL_SUPPORT": 6,
    "ENTITY_ONLY_MATCH": 5,
    "RELATION_ONLY_MATCH": 4,
    "CONTRADICTED": 3,
    "REQUIRES_REVIEW": 2,
    "NOT_SUPPORTED": 1,
}

NEGATION_CUES = ("不属于", "并非", "不是", "不适用于", "无关", "不支持")


@dataclass(slots=True)
class CurrentChineseSemanticUnit:
    semantic_unit_id: str
    semantic_unit_type: str
    unit: dict[str, Any]
    document: KnowledgeDocument
    chunks: list[KnowledgeChunk]
    source_spans: list[str]
    source_locator: dict[str, Any]
    grounding_passed: bool
    grounding_failures: list[str]
    source_kind: str = "SEMANTIC_UNIT"
    matched_chunk: KnowledgeChunk | None = None


class KGCurrentChineseEvidenceMatcher:
    """Matches existing graph facts to source-grounded current Chinese semantic units."""

    VERSION = "task25g_r2_current_chinese_matcher_v1"
    MAX_CANDIDATES_PER_FACT = 20

    STRUCTURED_FIELDS = (
        "device_models",
        "components",
        "alarm_codes",
        "alarm_names",
        "symptoms",
        "conditions",
        "causes",
        "actions",
        "procedure_steps",
        "prerequisites",
        "verification_steps",
        "safety_requirements",
        "communication_terms",
        "tools",
        "parts",
        "abort_conditions",
        "clearance_conditions",
    )

    def __init__(self, db: Session):
        self.db = db
        self.equivalence = KGCurrentEvidenceEquivalenceService()
        self.grounding_validator = SourceGroundingValidator()
        self._chunk_source_cache_key: tuple[str, ...] | None = None
        self._chunk_source_cache: list[
            tuple[KnowledgeChunk, list[CurrentChineseSemanticUnit], list[str]]
        ] = []

    @staticmethod
    def _normalize(value: str | None) -> str:
        return KnowledgeGraphFactIdentityService.normalize_key(value)

    @classmethod
    def _contains_any(cls, text: str, terms: Iterable[str]) -> tuple[bool, list[str]]:
        normalized_text = cls._normalize(text)
        hits: list[str] = []
        for term in terms:
            normalized_term = cls._normalize(term)
            if normalized_term and normalized_term in normalized_text:
                hits.append(term)
        return bool(hits), list(dict.fromkeys(hits))

    @classmethod
    def _structured_text(cls, unit: dict[str, Any]) -> str:
        values = [str(unit.get("title") or ""), str(unit.get("canonical_evidence") or "")]
        for field in cls.STRUCTURED_FIELDS:
            values.extend(str(value) for value in unit.get(field) or [])
        return "\n".join(values)

    @staticmethod
    def _source_spans(unit: dict[str, Any]) -> list[str]:
        values = [
            str(item.get("text") or "").strip()
            for item in unit.get("source_spans") or []
            if isinstance(item, dict)
        ]
        canonical = str(unit.get("canonical_evidence") or "").strip()
        if canonical and canonical not in values:
            values.insert(0, canonical)
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _document_is_current_engineering(document: KnowledgeDocument) -> bool:
        metadata = document.metadata_json or {}
        return bool(
            document.status == "active"
            and document.review_status == "approved"
            and document.parse_status == "parsed"
            and document.document_type != "marketing"
            and metadata.get("normalized_language") == "zh-CN"
            and metadata.get("engineering_approved_for_pilot") is True
            and metadata.get("approved_for_pilot") is True
            and bool(metadata.get("current_version", True))
            and not metadata.get("superseded_by_document_id")
        )

    def load_current_corpus(self) -> list[CurrentChineseSemanticUnit]:
        documents = list(self.db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id)))
        document_by_id = {document.id: document for document in documents if self._document_is_current_engineering(document)}
        chunks = list(
            self.db.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.document_id.in_(document_by_id), KnowledgeChunk.status == "active")
                .order_by(KnowledgeChunk.document_id, KnowledgeChunk.chunk_index, KnowledgeChunk.id)
            )
        )
        chunk_by_id = {str(chunk.id): chunk for chunk in chunks}
        anchors = list(
            self.db.scalars(
                select(MaintenanceSemanticAnchor)
                .where(
                    MaintenanceSemanticAnchor.document_id.in_(document_by_id),
                    MaintenanceSemanticAnchor.language == "zh-CN",
                    MaintenanceSemanticAnchor.current_version.is_(True),
                    MaintenanceSemanticAnchor.semantic_representation_version
                    == "task25b_r3_dev_r5_semantic_unit_v2",
                )
                .order_by(MaintenanceSemanticAnchor.id)
            )
        )
        result: dict[str, CurrentChineseSemanticUnit] = {}
        for anchor in anchors:
            unit = (anchor.semantic_fields or {}).get("semantic_unit") or {}
            unit_id = str(unit.get("semantic_unit_id") or (anchor.semantic_fields or {}).get("semantic_unit_id") or "")
            document = document_by_id.get(anchor.document_id)
            if not unit_id or document is None or unit_id in result:
                continue
            source_chunks = [
                chunk_by_id[str(chunk_id)]
                for chunk_id in unit.get("source_chunk_ids") or []
                if str(chunk_id) in chunk_by_id
            ]
            validation = self.grounding_validator.validate(unit, source_chunks, document)
            result[unit_id] = CurrentChineseSemanticUnit(
                semantic_unit_id=unit_id,
                semantic_unit_type=str(unit.get("semantic_unit_type") or unit.get("unit_type") or ""),
                unit=unit,
                document=document,
                chunks=source_chunks,
                source_spans=self._source_spans(unit),
                source_locator=unit.get("source_locator") or anchor.source_locator or {},
                grounding_passed=bool(validation.passed),
                grounding_failures=list(validation.failures),
            )
        return sorted(result.values(), key=lambda item: item.semantic_unit_id)

    @classmethod
    def _relation_hits(cls, spans: list[str], cues: Iterable[str]) -> tuple[bool, list[str]]:
        all_hits: list[str] = []
        for span in spans:
            _, hits = cls._contains_any(span, cues)
            all_hits.extend(hits)
        return bool(all_hits), list(dict.fromkeys(all_hits))

    @classmethod
    def _same_span_support(
        cls,
        spans: list[str],
        subject_terms: list[str],
        object_terms: list[str],
        relation_cues: tuple[str, ...],
    ) -> tuple[bool, list[dict[str, Any]]]:
        matches = []
        for index, span in enumerate(spans):
            subject, subject_hits = cls._contains_any(span, subject_terms)
            object_found, object_hits = cls._contains_any(span, object_terms)
            relation, relation_hits = cls._contains_any(span, relation_cues)
            if subject and object_found and relation:
                matches.append(
                    {
                        "span_index": index,
                        "span_sha256": stable_hash(span),
                        "subject_terms": subject_hits,
                        "object_terms": object_hits,
                        "relation_terms": relation_hits,
                    }
                )
        return bool(matches), matches

    @classmethod
    def _multi_span_support(
        cls,
        spans: list[str],
        subject_terms: list[str],
        object_terms: list[str],
        relation_cues: tuple[str, ...],
    ) -> tuple[bool, list[dict[str, Any]]]:
        subject_spans: list[dict[str, Any]] = []
        object_spans: list[dict[str, Any]] = []
        for index, span in enumerate(spans):
            subject, subject_hits = cls._contains_any(span, subject_terms)
            object_found, object_hits = cls._contains_any(span, object_terms)
            relation, relation_hits = cls._contains_any(span, relation_cues)
            if subject and relation:
                subject_spans.append(
                    {"span_index": index, "span_sha256": stable_hash(span), "subject_terms": subject_hits, "relation_terms": relation_hits}
                )
            if object_found and relation:
                object_spans.append(
                    {"span_index": index, "span_sha256": stable_hash(span), "object_terms": object_hits, "relation_terms": relation_hits}
                )
        combined = [*subject_spans[:2], *object_spans[:2]]
        distinct = {item["span_index"] for item in combined}
        return bool(subject_spans and object_spans and len(distinct) >= 2), combined

    @classmethod
    def _fact_scope(cls, fact: dict[str, Any], source: CurrentChineseSemanticUnit, text: str) -> dict[str, Any]:
        document = source.document
        unit = source.unit
        manufacturer = str(fact.get("manufacturer") or "").lower()
        doc_manufacturer = str(document.manufacturer or "").lower()
        manufacturer_compatible = not manufacturer or manufacturer == doc_manufacturer
        product_family = str(fact.get("product_family") or "")
        unit_family = str(unit.get("product_family") or document.product_series or "")
        family_term_match, _ = cls._contains_any(text, [product_family] if product_family else [])
        family_compatible = (
            not product_family
            or cls._normalize(product_family) == cls._normalize(unit_family)
            or family_term_match
        )
        model = str(fact.get("device_model") or "")
        unit_models = [str(value) for value in unit.get("device_models") or []]
        model_term_match, _ = cls._contains_any(text, [model] if model else [])
        model_compatible = not model or any(cls._normalize(model) == cls._normalize(value) for value in unit_models) or model_term_match
        alarm = str(fact.get("alarm_code") or "")
        unit_alarms = [str(value) for value in unit.get("alarm_codes") or []]
        alarm_term_match, _ = cls._contains_any(text, [alarm] if alarm else [])
        alarm_compatible = not alarm or any(cls._normalize(alarm) == cls._normalize(value) for value in unit_alarms) or alarm_term_match
        component = str(fact.get("component") or "")
        component_terms = [component] if component else []
        if fact.get("fact_kind") == "NODE" and fact.get("node_type") == "component":
            component_terms.extend(fact.get("entity_terms") or [])
        if fact.get("source_node_type") == "component":
            component_terms.extend(fact.get("source_terms") or [])
        if fact.get("target_node_type") == "component":
            component_terms.extend(fact.get("target_terms") or [])
        component_term_match, _ = cls._contains_any(text, component_terms)
        return {
            "manufacturer_compatible": manufacturer_compatible,
            "product_family_compatible": family_compatible,
            "model_compatible": model_compatible,
            "alarm_compatible": alarm_compatible,
            "component_compatible": not component or component_term_match,
            "product_family": unit_family,
            "product_family_term_match": family_term_match,
            "device_model": model if model_compatible else None,
            "model_term_match": model_term_match,
            "alarm_code": alarm if alarm_compatible else None,
            "alarm_term_match": alarm_term_match,
            "component": component if component_term_match else None,
            "component_term_match": component_term_match,
            "scope_valid": bool(
                manufacturer_compatible
                and family_compatible
                and model_compatible
                and alarm_compatible
                and (not component or component_term_match)
            ),
        }

    def _candidate(self, fact: dict[str, Any], source: CurrentChineseSemanticUnit) -> dict[str, Any] | None:
        unit = source.unit
        structured_text = self._structured_text(unit)
        spans = source.source_spans
        text = "\n".join([structured_text, *spans])
        fact_kind = fact["fact_kind"]
        if fact_kind == "NODE":
            subject_terms = list(fact.get("entity_terms") or [])
            subject_match, subject_hits = self._contains_any("\n".join(spans), subject_terms)
            object_match = True
            object_hits: list[str] = []
            relation_match = True
            relation_hits: list[str] = []
            same_span = subject_match
            same_span_details = []
            multi_span = False
            multi_span_details = []
            type_compatible = KGRelationEvidenceTypeMatrix.node_type_compatible(
                fact["node_type"], source.semantic_unit_type
            )
        else:
            subject_terms = list(fact.get("source_terms") or [])
            object_terms = list(fact.get("target_terms") or [])
            subject_match, subject_hits = self._contains_any("\n".join(spans), subject_terms)
            object_match, object_hits = self._contains_any("\n".join(spans), object_terms)
            rule = KGRelationEvidenceTypeMatrix.relation_rule(fact["relation_type"])
            if rule is None:
                return None
            relation_match, relation_hits = self._relation_hits(spans, rule.relation_cues)
            same_span, same_span_details = self._same_span_support(
                spans, subject_terms, object_terms, rule.relation_cues
            )
            multi_span, multi_span_details = self._multi_span_support(
                spans, subject_terms, object_terms, rule.relation_cues
            )
            type_compatible = KGRelationEvidenceTypeMatrix.relation_type_compatible(
                fact["relation_type"], source.semantic_unit_type
            )

        if fact_kind == "NODE" and not subject_match:
            return None
        if fact_kind == "EDGE" and not (subject_match or object_match or relation_match):
            return None
        locator = dict(source.source_locator or {})
        locator_valid = bool(
            locator.get("section")
            and locator.get("heading_path")
            and locator.get("source_chunk_ids")
            and locator.get("page_start") is not None
            and source.chunks
        )
        conflict = self._has_relevant_conflict(
            spans,
            subject_terms,
            object_terms if fact_kind == "EDGE" else [],
        )
        scope = self._fact_scope(fact, source, text)
        document_current = self._document_is_current_engineering(source.document)
        engineering_approved = bool(
            unit.get("source_grounded")
            and unit.get("engineering_verified")
            and unit.get("quality_status") == "ENGINEERING_VERIFIED_SOURCE_GROUNDED"
            and source.grounding_passed
        )
        entity_conflict = not bool(scope["manufacturer_compatible"] and scope["product_family_compatible"])
        base = {
            "fact_id": fact["fact_id"],
            "fact_kind": fact_kind,
            "fact_category": fact["fact_category"],
            "source_kind": source.source_kind,
            "semantic_unit_id": source.semantic_unit_id,
            "semantic_unit_type": source.semantic_unit_type,
            "document_id": str(source.document.id),
            "document_title": source.document.title,
            "document_type": source.document.document_type,
            "manufacturer": source.document.manufacturer,
            "source_chunk_ids": [str(chunk.id) for chunk in source.chunks],
            "chunk_id": str(source.matched_chunk.id) if source.matched_chunk else (
                str(source.chunks[0].id) if source.chunks else None
            ),
            "source_locator": {
                "document_id": str(source.document.id),
                "semantic_unit_id": source.semantic_unit_id,
                **locator,
            },
            "language": unit.get("language") or (source.document.metadata_json or {}).get("normalized_language"),
            "document_current": document_current,
            "engineering_approved": engineering_approved,
            "locator_valid": locator_valid,
            "subject_match": subject_match,
            "subject_terms": subject_hits,
            "object_match": object_match,
            "object_terms": object_hits,
            "relation_match": relation_match,
            "relation_terms": relation_hits,
            "same_span_support": same_span,
            "same_span_details": same_span_details,
            "multi_span_support": multi_span,
            "multi_span_details": multi_span_details,
            "type_compatible": type_compatible,
            "conflict": conflict,
            "entity_conflict": entity_conflict,
            "source_grounding_failures": source.grounding_failures,
            "canonical_evidence_sha256": stable_hash(unit.get("canonical_evidence") or ""),
            **scope,
        }
        equivalence = self.equivalence.evaluate(fact, base)
        if conflict:
            support = "CONTRADICTED"
        elif equivalence["passed"] and same_span:
            support = "DIRECT_EXACT_SUPPORT"
        elif equivalence["passed"] and multi_span:
            support = "DIRECT_MULTI_SOURCE_SUPPORT"
        elif subject_match and object_match and not relation_match:
            support = "ENTITY_ONLY_MATCH"
        elif relation_match and not (subject_match and object_match):
            support = "RELATION_ONLY_MATCH"
        elif subject_match or object_match:
            support = "PARTIAL_SUPPORT"
        elif type_compatible:
            support = "REQUIRES_REVIEW"
        else:
            support = "NOT_SUPPORTED"
        candidate_core = {
            **base,
            "support_level": support,
            "equivalence": equivalence,
            "automatic_binding_eligible": support in {"DIRECT_EXACT_SUPPORT", "DIRECT_MULTI_SOURCE_SUPPORT"},
            "review_required": support not in {"DIRECT_EXACT_SUPPORT", "DIRECT_MULTI_SOURCE_SUPPORT"},
            "reason": self._reason(support, equivalence, source, fact_kind),
            "matcher_version": self.VERSION,
            "relation_matrix_version": KGRelationEvidenceTypeMatrix.VERSION,
        }
        candidate_core["candidate_id"] = "kgem_" + stable_hash(
            [
                fact["identity_hash"],
                source.source_kind,
                source.semantic_unit_id,
                candidate_core["chunk_id"],
                support,
                candidate_core["source_locator"],
            ]
        )[:48]
        candidate_core["candidate_hash"] = stable_hash(candidate_core)
        return candidate_core

    @staticmethod
    def _reason(
        support: str,
        equivalence: dict[str, Any],
        source: CurrentChineseSemanticUnit,
        fact_kind: str,
    ) -> str:
        if support == "DIRECT_EXACT_SUPPORT":
            if fact_kind == "NODE":
                return "one current Chinese source span explicitly matches the complete node identity"
            return "one current Chinese source span explicitly matches subject, relation, and object"
        if support == "DIRECT_MULTI_SOURCE_SUPPORT":
            return "multiple located spans in one grounded semantic unit jointly support the complete fact"
        if support == "CONTRADICTED":
            return "source contains an explicit negation or incompatibility cue"
        failures = list(equivalence.get("failure_reasons") or [])
        failures.extend(source.grounding_failures)
        return ",".join(dict.fromkeys(failures)) or support.lower()

    @classmethod
    def _has_relevant_conflict(
        cls,
        spans: Iterable[str],
        subject_terms: Iterable[str],
        object_terms: Iterable[str],
    ) -> bool:
        for span in spans:
            sentences = [
                value
                for value in re.split(r"(?<=[。！？；])\s*|\n+", span)
                if value.strip()
            ]
            for sentence in sentences:
                normalized = cls._normalize(sentence)
                if not any(cls._normalize(cue) in normalized for cue in NEGATION_CUES):
                    continue
                subject_match, _ = cls._contains_any(sentence, subject_terms)
                object_values = list(object_terms)
                object_match = not object_values or cls._contains_any(sentence, object_values)[0]
                if subject_match and object_match:
                    return True
        return False

    def _prepared_chunk_sources(
        self,
        corpus: list[CurrentChineseSemanticUnit],
    ) -> list[tuple[KnowledgeChunk, list[CurrentChineseSemanticUnit], list[str]]]:
        cache_key = tuple(sorted(source.semantic_unit_id for source in corpus))
        if cache_key == self._chunk_source_cache_key:
            return self._chunk_source_cache

        units_by_chunk: dict[str, list[CurrentChineseSemanticUnit]] = {}
        chunks: dict[str, KnowledgeChunk] = {}
        for source in corpus:
            for chunk in source.chunks:
                chunk_id = str(chunk.id)
                chunks[chunk_id] = chunk
                units_by_chunk.setdefault(chunk_id, []).append(source)

        prepared = []
        for chunk_id in sorted(chunks):
            chunk = chunks[chunk_id]
            sentences = [
                " ".join(value.split())
                for value in re.split(r"(?<=[。！？；])\s*|\n+", chunk.content or "")
                if " ".join(value.split())
            ]
            prepared.append((chunk, units_by_chunk.get(chunk_id, []), sentences))

        self._chunk_source_cache_key = cache_key
        self._chunk_source_cache = prepared
        return prepared

    def match_fact(
        self,
        fact: dict[str, Any],
        corpus: list[CurrentChineseSemanticUnit] | None = None,
    ) -> list[dict[str, Any]]:
        active_corpus = corpus if corpus is not None else self.load_current_corpus()
        candidates = [
            candidate
            for source in active_corpus
            if (candidate := self._candidate(fact, source)) is not None
        ]
        if fact["fact_kind"] == "EDGE":
            candidates.extend(self._chunk_edge_candidates(fact, active_corpus))
        candidates = list({item["candidate_id"]: item for item in candidates}.values())
        candidates.sort(
            key=lambda item: (
                -SUPPORT_PRIORITY[item["support_level"]],
                not item["scope_valid"],
                not item["locator_valid"],
                item["candidate_id"],
            )
        )
        return candidates[: self.MAX_CANDIDATES_PER_FACT]

    def _chunk_edge_candidates(
        self,
        fact: dict[str, Any],
        corpus: list[CurrentChineseSemanticUnit],
    ) -> list[dict[str, Any]]:
        rule = KGRelationEvidenceTypeMatrix.relation_rule(fact["relation_type"])
        if rule is None:
            return []
        result: list[dict[str, Any]] = []
        for chunk, source_units, sentences in self._prepared_chunk_sources(corpus):
            chunk_id = str(chunk.id)
            compatible_units = [
                source
                for source in source_units
                if source.grounding_passed
                and KGRelationEvidenceTypeMatrix.relation_type_compatible(
                    fact["relation_type"], source.semantic_unit_type
                )
            ]
            if not compatible_units:
                continue
            matched_sentences = []
            for sentence in sentences:
                subject, _ = self._contains_any(sentence, fact.get("source_terms") or [])
                object_found, _ = self._contains_any(sentence, fact.get("target_terms") or [])
                relation, _ = self._contains_any(sentence, rule.relation_cues)
                if subject and object_found and relation:
                    matched_sentences.append(sentence)
            if not matched_sentences:
                continue
            source = sorted(compatible_units, key=lambda item: (item.semantic_unit_type, item.semantic_unit_id))[0]
            metadata = chunk.metadata_json or {}
            locator = metadata.get("source_locator") if isinstance(metadata.get("source_locator"), dict) else {}
            locator = {
                "section": locator.get("section") or chunk.section_title or "source_chunk",
                "heading_path": locator.get("heading_path") or metadata.get("heading_path") or [chunk.section_title or "source_chunk"],
                "page_start": locator.get("page_start") if locator.get("page_start") is not None else chunk.page_number,
                "page_end": locator.get("page_end") if locator.get("page_end") is not None else chunk.page_number,
                "source_chunk_ids": [chunk_id],
                **locator,
            }
            chunk_source = CurrentChineseSemanticUnit(
                semantic_unit_id=source.semantic_unit_id,
                semantic_unit_type=source.semantic_unit_type,
                unit=source.unit,
                document=source.document,
                chunks=source.chunks,
                source_spans=matched_sentences,
                source_locator=locator,
                grounding_passed=source.grounding_passed,
                grounding_failures=source.grounding_failures,
                source_kind="SOURCE_CHUNK",
                matched_chunk=chunk,
            )
            candidate = self._candidate(fact, chunk_source)
            if candidate is not None:
                result.append(candidate)
        return result

    def match_facts(self, facts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        corpus = self.load_current_corpus()
        return [
            {
                "fact": fact,
                "candidates": self.match_fact(fact, corpus),
            }
            for fact in facts
        ]
