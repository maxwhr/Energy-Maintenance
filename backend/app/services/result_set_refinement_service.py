from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.services.query_understanding_service import QueryUnderstanding, normalize_alarm_identifier, normalize_device_model

if TYPE_CHECKING:
    from app.services.hybrid_retrieval_service import HybridScoredCandidate


@dataclass(frozen=True, slots=True)
class ResultSetRefinement:
    surfaced: list["HybridScoredCandidate"]
    diagnostics: dict


class ResultSetRefinementService:
    """Collapse redundant evidence for presentation without changing raw evaluation rankings."""

    def __init__(self, *, score_threshold: float = 0.20, margin_threshold: float = 0.16) -> None:
        self.score_threshold = score_threshold
        self.margin_threshold = margin_threshold

    @staticmethod
    def _section_key(item: "HybridScoredCandidate") -> str:
        metadata = item.chunk.metadata_json or {}
        locator = metadata.get("heading_path") or metadata.get("source_locator") or item.chunk.section_title
        fallback_locator = f"page:{item.chunk.page_number or 'unknown'}"
        return f"{item.document.id}:{str(locator or fallback_locator).strip().lower()}"

    @staticmethod
    def _content_key(item: "HybridScoredCandidate") -> str:
        value = re.sub(r"\s+", "", (item.chunk.content or "").lower())
        return value[:260] or str(item.chunk.id)

    @staticmethod
    def _anchors_match(item: "HybridScoredCandidate", analysis: QueryUnderstanding | None) -> bool:
        if analysis is None:
            return True
        text = " ".join((item.document.title or "", item.document.product_series or "", item.document.model or "",
                         item.chunk.section_title or "", item.chunk.content or "",
                         " ".join(str(value) for value in ((item.document.metadata_json or {}).get("device_models") or []))))
        normalized_model_text = normalize_device_model(text)
        normalized_alarm_text = normalize_alarm_identifier(text)
        if analysis.device_models and not any(normalize_device_model(model) in normalized_model_text for model in analysis.device_models):
            return False
        if analysis.fault_codes and not any(normalize_alarm_identifier(code) in normalized_alarm_text for code in analysis.fault_codes):
            return False
        return True

    def refine(
        self,
        raw: list["HybridScoredCandidate"],
        *,
        requested_top_k: int,
        analysis: QueryUnderstanding | None,
    ) -> ResultSetRefinement:
        raw = list(raw)
        limit = max(1, min(5, int(requested_top_k)))
        top_score = float(raw[0].score) if raw else 0.0
        used_sections: set[str] = set()
        used_content: set[str] = set()
        per_document: dict[object, int] = {}
        surfaced: list["HybridScoredCandidate"] = []
        section_collapses = document_collapses = duplicate_collapses = low_score_cutoffs = 0
        cutoff_reason = "MAX_K"
        for position, item in enumerate(raw):
            section = self._section_key(item)
            content = self._content_key(item)
            if section in used_sections:
                section_collapses += 1
                cutoff_reason = "SAME_SECTION_COLLAPSE"
                continue
            if content in used_content:
                duplicate_collapses += 1
                cutoff_reason = "DUPLICATE_COLLAPSE"
                continue
            if per_document.get(item.document.id, 0) >= 2:
                document_collapses += 1
                cutoff_reason = "SAME_DOCUMENT_COLLAPSE"
                continue
            # An exact model/alarm conflict is never promoted merely to fill Top-K.
            if not self._anchors_match(item, analysis):
                low_score_cutoffs += 1
                cutoff_reason = "EXACT_MISMATCH"
                continue
            score = float(item.score)
            if position > 0 and score < self.score_threshold:
                low_score_cutoffs += 1
                cutoff_reason = "LOW_SCORE"
                break
            if position > 0 and top_score and (top_score - score) >= self.margin_threshold and len(surfaced) >= 1:
                cutoff_reason = "LARGE_SCORE_DROP"
                break
            surfaced.append(item)
            used_sections.add(section); used_content.add(content)
            per_document[item.document.id] = per_document.get(item.document.id, 0) + 1
            if len(surfaced) >= limit:
                cutoff_reason = "MAX_K"
                break
        if raw and not surfaced:
            # Never turn a non-empty raw ranking into an empty result merely to improve display precision.
            surfaced = [raw[0]]
            cutoff_reason = "INSUFFICIENT_EVIDENCE"
        return ResultSetRefinement(surfaced=surfaced, diagnostics={
            "requested_top_k": requested_top_k, "raw_candidate_count": len(raw), "raw_top_k": min(10, len(raw)),
            "evaluated_top_k": min(5, len(raw)), "surfaced_top_k": len(surfaced), "cutoff_reason": cutoff_reason,
            "score_threshold": self.score_threshold, "margin_threshold": self.margin_threshold,
            "section_collapses": section_collapses, "document_collapses": document_collapses,
            "duplicate_collapses": duplicate_collapses, "low_score_cutoffs": low_score_cutoffs,
            "section_diversity": len({self._section_key(item) for item in surfaced}),
            "document_diversity": len({str(item.document.id) for item in surfaced}),
            "collapsed_groups": section_collapses + document_collapses + duplicate_collapses,
        })

    def refine_query_aware(self, raw: list[Any], *, requested_top_k: int) -> ResultSetRefinement:
        """Collapse Query-Aware candidates while preserving every evidence locator and source id."""
        group_index: dict[tuple[str, str], Any] = {}
        group_order: list[tuple[str, str]] = []
        collapse_groups: list[dict[str, Any]] = []
        drop_records: list[dict[str, Any]] = []
        for item in raw:
            if not item.scope_validation_passed:
                drop_records.append({"candidate_id": item.candidate_id, "reason": "SCOPE_VALIDATION_FAILED"})
                continue
            identity = item.evidence_equivalence_key or item.evidence_identity or item.semantic_unit_id or str(
                (item.source_locator or {}).get("heading_path")
                or (item.source_locator or {}).get("section")
                or item.section_title
                or f"page:{item.page_number}"
            ).strip().lower()
            key = ("" if item.evidence_equivalence_key else item.document_id, identity)
            existing = group_index.get(key)
            if existing is not None:
                existing_quality = (
                    float(getattr(existing, "direct_answer_score", 0.0)),
                    float(getattr(existing, "requested_information_coverage", 0.0)),
                    -float(getattr(existing, "generality_penalty", 0.0)),
                    float(existing.final_score),
                )
                item_quality = (
                    float(getattr(item, "direct_answer_score", 0.0)),
                    float(getattr(item, "requested_information_coverage", 0.0)),
                    -float(getattr(item, "generality_penalty", 0.0)),
                    float(item.final_score),
                )
                survivor, merged = (item, existing) if item_quality > existing_quality else (existing, item)
                before = list(survivor.source_chunk_ids)
                survivor.merge_from(merged)
                locators = list((survivor.source_locator or {}).get("merged_locators") or [])
                for locator in (survivor.source_locator, merged.source_locator):
                    if locator and locator not in locators:
                        locators.append(locator)
                survivor.source_locator = {**(survivor.source_locator or {}), "merged_locators": locators}
                pages = [value for value in (survivor.page_number, merged.page_number) if value is not None]
                survivor.page_number = min(pages) if pages else None
                group_index[key] = survivor
                collapse_groups.append({
                    "kept_candidate_id": survivor.candidate_id,
                    "merged_candidate_id": merged.candidate_id,
                    "reason": "HIGHER_DIRECT_ANSWER_SURVIVOR",
                    "identity": identity,
                    "source_chunk_ids_added": [value for value in survivor.source_chunk_ids if value not in before],
                    "requested_information_support": sorted(survivor.requested_information_support),
                })
                continue
            group_index[key] = item
            group_order.append(key)
        all_survivors = [group_index[key] for key in group_order]
        surfaced = all_survivors[:max(1, requested_top_k)]
        for item in all_survivors[max(1, requested_top_k):]:
            drop_records.append({"candidate_id": item.candidate_id, "reason": "PRESENTATION_TOP_K"})
        if raw and not surfaced:
            surfaced = [raw[0]]
        return ResultSetRefinement(surfaced=surfaced, diagnostics={
            "requested_top_k": requested_top_k,
            "raw_candidate_count": len(raw),
            "surfaced_top_k": len(surfaced),
            "collapsed_groups": collapse_groups,
            "collapsed_group_count": len(collapse_groups),
            "evidence_preserving_merges": len(collapse_groups),
            "drop_records": drop_records,
            "relevant_candidates_lost_without_reason": 0,
        })
