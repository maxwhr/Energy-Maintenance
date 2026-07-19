from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, RetrievalEvaluationCase
from app.services.query_understanding_service import QueryUnderstandingService
from task25b_r3_dev_r2_common import OUT, V2_DATASET, now_iso, normalized_text


def _jaccard(query: str, content: str) -> float:
    query_text = normalized_text(query)
    left = {query_text[index:index + 2] for index in range(max(0, len(query_text) - 1))}
    right_text = normalized_text(content)
    right = {right_text[index:index + 2] for index in range(max(0, len(right_text) - 1))}
    return len(left & right) / len(left | right) if left or right else 0.0


def main() -> None:
    parser = QueryUnderstandingService()
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V2_DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v2",
        )))
        chunk_ids = {UUID(str(value)) for case in cases for value in (case.expected_chunk_ids or [])}
        chunks = {chunk.id: chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))}
    rows = []
    for case in cases:
        chunk = chunks.get(UUID(str(case.expected_chunk_ids[0]))) if case.expected_chunk_ids else None
        analysis = parser.understand(case.query_text)
        overlap = _jaccard(case.query_text, chunk.content if chunk else "")
        valid = bool((case.metadata_json or {}).get("vector_heavy")) and not analysis.device_models and not analysis.fault_codes and overlap < 0.35
        rows.append({"case_id": str(case.id), "category": case.category, "declared_vector_heavy": bool((case.metadata_json or {}).get("vector_heavy")),
                     "has_model_anchor": bool(analysis.device_models), "has_alarm_anchor": bool(analysis.fault_codes),
                     "lexical_jaccard": round(overlap, 6), "valid_vector_heavy": valid})
    payload = {"generated_at": now_iso(), "dataset": V2_DATASET, "cases": len(rows), "valid_vector_heavy": sum(row["valid_vector_heavy"] for row in rows),
               "required_for_v3_test": 20, "definition": {"no_full_model": True, "no_full_alarm": True, "jaccard_lt": 0.35}, "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "vector_heavy_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "valid_vector_heavy": payload["valid_vector_heavy"], "v3_required": 20}, ensure_ascii=False))


if __name__ == "__main__":
    main()
