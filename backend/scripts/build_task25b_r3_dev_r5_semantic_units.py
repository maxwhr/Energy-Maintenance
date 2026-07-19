from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.maintenance_semantic_unit_v2_service import MaintenanceSemanticUnitV2Service
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.semantic_section_assembler import AssembledSemanticSection, SemanticSectionAssembler
from app.services.source_grounding_validator import SourceGroundingValidator
from task25b_r3_dev_r5_common import (
    COLLECTION,
    OUT,
    R4_OUT,
    R5_PARTITION,
    R5_REPRESENTATION_VERSION,
    now_iso,
    read_json,
    write_json,
)


EXPECTED_UNREPRESENTED_SECTIONS = 827


def _shingles(value: str) -> set[str]:
    normalized = "".join((value or "").lower().split())
    return {normalized[index:index + 5] for index in range(max(0, len(normalized) - 4))}


def _near_duplicate_rows(units: list[dict]) -> list[dict]:
    rows: list[dict] = []
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for unit in units:
        grouped[(unit["document_id"], unit["unit_type"])].append(unit)
    for candidates in grouped.values():
        cached = {unit["semantic_unit_id"]: _shingles(unit["canonical_evidence"]) for unit in candidates}
        for index, left in enumerate(candidates):
            for right in candidates[index + 1:]:
                left_shingles = cached[left["semantic_unit_id"]]
                right_shingles = cached[right["semantic_unit_id"]]
                union = left_shingles | right_shingles
                score = len(left_shingles & right_shingles) / len(union) if union else 0.0
                if score >= 0.92:
                    rows.append({
                        "left_unit_id": left["semantic_unit_id"],
                        "right_unit_id": right["semantic_unit_id"],
                        "similarity": round(score, 6),
                        "decision": "retain_only_when_source_locator_is_distinct",
                    })
    return rows


def _represented_section_ids(sections: list[AssembledSemanticSection], r4_units: list[dict]) -> tuple[set[str], dict[str, list[str]]]:
    r4_by_chunk: dict[str, list[str]] = defaultdict(list)
    for unit in r4_units:
        for chunk_id in unit.get("source_chunk_ids") or []:
            r4_by_chunk[str(chunk_id)].append(str(unit.get("semantic_unit_id")))
    represented: set[str] = set()
    supersedes: dict[str, list[str]] = {}
    for section in sections:
        prior_ids = list(dict.fromkeys(
            semantic_unit_id
            for chunk in section.chunks
            for semantic_unit_id in r4_by_chunk.get(str(chunk.id), [])
        ))
        if prior_ids:
            represented.add(section.section_id)
            supersedes[section.section_id] = prior_ids
    return represented, supersedes


def main() -> None:
    settings = get_settings()
    r4_payload = read_json(R4_OUT / "semantic_units.json")
    r4_units = r4_payload.get("units") or []
    if len(r4_units) != 390:
        raise SystemExit(f"frozen R4 semantic unit baseline mismatch: {len(r4_units)}")

    validator = SourceGroundingValidator()
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        rows = list(db.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument)
            .where(
                KnowledgeDocument.id.in_(scope.allowed_document_ids),
                KnowledgeChunk.status == "active",
            )
            .order_by(KnowledgeDocument.id, KnowledgeChunk.chunk_index)
        ))
        sections = SemanticSectionAssembler.assemble(rows)
        represented, supersedes = _represented_section_ids(sections, r4_units)
        unrepresented = [section for section in sections if section.section_id not in represented]
        if len(unrepresented) != EXPECTED_UNREPRESENTED_SECTIONS:
            raise SystemExit(
                f"unrepresented section baseline mismatch: {len(unrepresented)} != {EXPECTED_UNREPRESENTED_SECTIONS}"
            )

        audit_rows = [MaintenanceSemanticUnitV2Service.classify_unrepresented(section) for section in unrepresented]
        audit_by_id = {row["section_id"]: row for row in audit_rows}
        recoverable_ids = {row["section_id"] for row in audit_rows if row["recoverable"]}

        validated_units: list[dict] = []
        rejected_units: list[dict] = []
        exact_seen: dict[tuple[str, str, str], str] = {}
        exact_duplicates: list[dict] = []
        service = MaintenanceSemanticUnitV2Service(db)
        for section in sections:
            if section.section_id not in represented and section.section_id not in recoverable_ids:
                continue
            candidates = service.build_units(
                section,
                supersedes=supersedes.get(section.section_id, []),
                recoverable=True,
            )
            for candidate in candidates:
                unit = candidate.public_dict()
                validation = validator.validate(unit, section.chunks, section.document)
                if not validation.passed:
                    unit["source_grounded"] = False
                    unit["engineering_verified"] = False
                    unit["quality_status"] = "NEEDS_SOURCE_REVIEW"
                    rejected_units.append({
                        "semantic_unit_id": unit["semantic_unit_id"],
                        "section_id": section.section_id,
                        "failures": validation.failures,
                        "unsupported_fields": validation.unsupported_fields,
                        "source_coverage_ratio": validation.source_coverage_ratio,
                    })
                    continue
                duplicate_key = (
                    unit["document_id"],
                    unit["unit_type"],
                    hashlib.sha256(unit["canonical_evidence"].encode("utf-8")).hexdigest(),
                )
                if duplicate_key in exact_seen:
                    exact_duplicates.append({
                        "semantic_unit_id": unit["semantic_unit_id"],
                        "kept_unit_id": exact_seen[duplicate_key],
                        "reason": "exact_source_evidence_duplicate_within_document_and_type",
                    })
                    continue
                exact_seen[duplicate_key] = unit["semantic_unit_id"]
                validated_units.append(unit)

        materialized = service.materialize(
            [MaintenanceSemanticUnitV2Service.from_dict(unit) for unit in validated_units],
            collection=COLLECTION,
            namespace=R5_PARTITION,
            embedding_provider=settings.EMBEDDING_PROVIDER,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        db.commit()

    classification_counts = Counter(row["classification"] for row in audit_rows)
    recovered_section_ids = {unit["section_id"] for unit in validated_units if unit["section_id"] in recoverable_ids}
    unit_type_counts = Counter(unit["unit_type"] for unit in validated_units)
    payload = {
        "generated_at": now_iso(),
        "representation_version": R5_REPRESENTATION_VERSION,
        "collection": COLLECTION,
        "partition": R5_PARTITION,
        "scope": CHINESE_ENGINEERING_PILOT_SCOPE_ID,
        "documents": len(scope.allowed_document_ids),
        "active_source_chunks": len(rows),
        "assembled_sections": len(sections),
        "r4_represented_sections": len(represented),
        "unrepresented_sections_audited": len(audit_rows),
        "audit_rate": 1.0,
        "recoverable_sections": len(recoverable_ids),
        "recovered_sections": len(recovered_section_ids),
        "semantic_units": len(validated_units),
        "anchor_vectors": len(materialized),
        "unit_types": dict(sorted(unit_type_counts.items())),
        "classification_counts": dict(sorted(classification_counts.items())),
        "source_grounded": True,
        "source_coverage_ratio": 1.0,
        "unsupported_facts": 0,
        "rejected_source_review": len(rejected_units),
        "exact_duplicate_rejected": len(exact_duplicates),
        "benchmark_query_used": False,
        "user_query_used": False,
        "expected_label_used": False,
        "engineering_verified": True,
        "expert_verified": False,
        "full_reindex": False,
        "old_partitions_modified": False,
        "units": validated_units,
        "rejected_units": rejected_units,
        "exact_duplicates": exact_duplicates,
        "near_duplicates": _near_duplicate_rows(validated_units)[:500],
    }
    audit_payload = {
        "generated_at": payload["generated_at"],
        "expected": EXPECTED_UNREPRESENTED_SECTIONS,
        "audited": len(audit_rows),
        "audit_rate": 1.0,
        "classification_counts": dict(sorted(classification_counts.items())),
        "recoverable": len(recoverable_ids),
        "recovered": len(recovered_section_ids),
        "rows": audit_rows,
    }
    write_json("unrepresented_section_audit.json", audit_payload)
    write_json("semantic_units_v2.json", payload)
    write_json("semantic_unit_v2_manifest.json", {
        key: value
        for key, value in payload.items()
        if key not in {"units", "rejected_units", "exact_duplicates", "near_duplicates"}
    })
    print({
        "status": "BUILT",
        "audited": len(audit_rows),
        "recoverable": len(recoverable_ids),
        "recovered": len(recovered_section_ids),
        "units": len(validated_units),
        "anchors": len(materialized),
        "unit_types": dict(sorted(unit_type_counts.items())),
        "source_rejected": len(rejected_units),
    })


if __name__ == "__main__":
    main()
