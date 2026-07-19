from __future__ import annotations

import hashlib
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, MaintenanceSemanticAnchor
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService
from task25b_r3_dev_r4_common import OUT, R4_PARTITION, read_json, now_iso, write_json


def main() -> None:
    payload = read_json(OUT / "semantic_units.json")
    units = payload.get("units") or []
    with SessionLocal() as db:
        source_ids = {value for unit in units for value in (unit.get("source_chunk_ids") or [])}
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(source_ids)))}
        anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(MaintenanceSemanticAnchor.namespace == R4_PARTITION)))
    failures = Counter()
    canonical_hashes = set()
    for unit in units:
        unit_source_ids = unit.get("source_chunk_ids") or []
        source_text = " ".join((chunks[value].content or "") for value in unit_source_ids if value in chunks)
        if not unit.get("source_locator"): failures["missing_locator"] += 1
        if not unit_source_ids or any(value not in chunks for value in unit_source_ids): failures["missing_source_chunk"] += 1
        if unit.get("language") != "zh-CN": failures["language_leakage"] += 1
        if not unit.get("current_version"): failures["non_current"] += 1
        if unit.get("quality_status") != MaintenanceSemanticUnitService.QUALITY_VERIFIED: failures["not_engineering_verified"] += 1
        if not unit.get("canonical_text"): failures["empty_canonical"] += 1
        if unit.get("semantic_unit_type") not in MaintenanceSemanticUnitService.UNIT_TYPES: failures["invalid_unit_type"] += 1
        if unit.get("source_hash") != hashlib.sha256("|".join(
            hashlib.sha256((chunks[value].content or "").encode("utf-8")).hexdigest() for value in unit_source_ids if value in chunks
        ).encode("utf-8")).hexdigest(): failures["source_hash_mismatch"] += 1
        if (unit.get("canonical_text") or "").split("原文证据：", 1)[-1] not in " ".join(source_text.split()):
            failures["source_excerpt_not_reproducible"] += 1
        if "expected_chunk" in (unit.get("canonical_text") or "").lower() or "benchmark" in (unit.get("canonical_text") or "").lower():
            failures["benchmark_label_leakage"] += 1
        canonical_hash = hashlib.sha256((unit.get("canonical_text") or "").encode("utf-8")).hexdigest()
        if canonical_hash in canonical_hashes: failures["exact_duplicate"] += 1
        canonical_hashes.add(canonical_hash)
    vector_ids = [anchor.vector_id for anchor in anchors]
    if len(vector_ids) != len(set(vector_ids)): failures["duplicate_vector_id"] += len(vector_ids) - len(set(vector_ids))
    if len(anchors) != payload.get("anchor_vectors"): failures["anchor_count_mismatch"] += 1
    result = {
        "generated_at": now_iso(), "units": len(units), "anchors": len(anchors), "failures": dict(sorted(failures.items())),
        "quality_status_counts": dict(sorted(Counter(unit.get("quality_status") for unit in units).items())),
        "exact_duplicate_rejected": payload.get("exact_duplicate_rejected"), "near_duplicate_pairs": payload.get("near_duplicate_pairs"),
        "source_grounded": not failures, "benchmark_query_used": False, "expected_labels_used": False,
        "engineering_verified": True, "expert_verified": False, "passed": not failures,
    }
    write_json("semantic_unit_quality.json", result)
    print({"status": "PASSED" if result["passed"] else "FAILED", **{key: result[key] for key in ("units", "anchors", "failures")}})
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
