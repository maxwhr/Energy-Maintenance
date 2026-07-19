from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService
from app.services.retrieval_scope_service import RetrievalScopeService
from task25b_r3_dev_r4_common import COLLECTION, OUT, R4_PARTITION, REPRESENTATION_VERSION, now_iso, write_json


def shingles(value: str) -> set[str]:
    normalized = re.sub(r"\s+", "", value.lower())
    return {normalized[index:index + 5] for index in range(max(0, len(normalized) - 4))}


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def main() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        rows = list(db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.id.in_(scope.allowed_document_ids), KnowledgeChunk.status == "active",
        ).order_by(KnowledgeDocument.id, KnowledgeChunk.chunk_index)))
        service = MaintenanceSemanticUnitService(db)
        candidates = []
        rejected_reasons = Counter()
        all_sections = set()
        for chunk, document in rows:
            section_key = (str(document.id), str(chunk.section_title or chunk.chunk_index))
            all_sections.add(section_key)
            unit = service.build_unit([chunk], document)
            if unit is None:
                _, reason = service.is_eligible([chunk])
                rejected_reasons[reason] += 1
                continue
            candidates.append(unit)
        unique = []
        exact_seen = {}
        duplicate_rows = []
        for unit in candidates:
            canonical_hash = hashlib.sha256(unit.canonical_text.encode("utf-8")).hexdigest()
            key = (unit.semantic_unit_type, canonical_hash)
            if key in exact_seen:
                duplicate_rows.append({"semantic_unit_id": unit.semantic_unit_id, "kept_unit_id": exact_seen[key], "reason": "exact_duplicate"})
                continue
            exact_seen[key] = unit.semantic_unit_id
            unique.append(unit)
        if not 300 <= len(unique) <= 600:
            raise SystemExit(f"semantic unit count outside controlled target: {len(unique)}")
        anchor_count = sum(len(unit.anchor_types) for unit in unique)
        if not 800 <= anchor_count <= 1500:
            raise SystemExit(f"anchor count outside controlled target: {anchor_count}")
        near_duplicate_rows = []
        by_document: dict[str, list] = defaultdict(list)
        for unit in unique:
            by_document[unit.document_id].append(unit)
        for document_units in by_document.values():
            cached = {unit.semantic_unit_id: shingles(unit.canonical_text) for unit in document_units}
            for index, left in enumerate(document_units):
                for right in document_units[index + 1:]:
                    score = jaccard(cached[left.semantic_unit_id], cached[right.semantic_unit_id])
                    if score >= 0.92:
                        near_duplicate_rows.append({
                            "left_unit_id": left.semantic_unit_id, "right_unit_id": right.semantic_unit_id,
                            "similarity": round(score, 6), "decision": "retain_distinct_source_locator",
                        })
        materialized = service.materialize(
            unique, collection=COLLECTION, namespace=R4_PARTITION,
            embedding_provider=settings.EMBEDDING_PROVIDER, embedding_model=settings.EMBEDDING_MODEL,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        db.commit()
        unit_payloads = [unit.public_dict() for unit in unique]
        represented_sections = {(unit.document_id, unit.source_section) for unit in unique}
        payload = {
            "generated_at": now_iso(), "representation_version": REPRESENTATION_VERSION,
            "collection": COLLECTION, "partition": R4_PARTITION, "scope": CHINESE_ENGINEERING_PILOT_SCOPE_ID,
            "documents": len(scope.allowed_document_ids), "active_source_chunks": len(rows), "eligible_sections": len(unique),
            "semantic_units": len(unique), "anchor_vectors": len(materialized),
            "unit_types": dict(sorted(Counter(unit.semantic_unit_type for unit in unique).items())),
            "anchor_types": dict(sorted(Counter(anchor for unit in unique for anchor in unit.anchor_types).items())),
            "document_coverage": len({unit.document_id for unit in unique}),
            "product_coverage": dict(sorted(Counter(unit.product_family for unit in unique).items())),
            "unrepresented_sections": len(all_sections) - len(represented_sections),
            "unrepresented_reasons": dict(sorted(rejected_reasons.items())),
            "exact_duplicate_rejected": len(duplicate_rows), "near_duplicate_pairs": len(near_duplicate_rows),
            "near_duplicate_policy": "retain only with distinct source locator; no relevance expansion",
            "source_only": True, "benchmark_query_used": False, "expected_label_used": False,
            "engineering_verified": True, "expert_verified": False, "test_data_used": False,
            "units": unit_payloads, "rejected_duplicates": duplicate_rows, "near_duplicates": near_duplicate_rows[:200],
        }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json("semantic_units.json", payload)
    write_json("semantic_unit_manifest.json", {key: value for key, value in payload.items() if key not in {"units", "near_duplicates", "rejected_duplicates"}})
    print({"status": "BUILT", "documents": payload["document_coverage"], "units": len(unique), "anchors": len(materialized), "unit_types": payload["unit_types"]})


if __name__ == "__main__":
    main()

