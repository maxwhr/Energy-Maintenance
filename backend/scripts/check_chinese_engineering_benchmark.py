from __future__ import annotations

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase
from generate_chinese_engineering_benchmark import DATASET
from task25b_r3_dev_common import now_iso, write_json


def main() -> None:
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET)))
    counts = {"cases": len(cases), "vector_heavy": sum(bool((x.metadata_json or {}).get("vector_heavy")) for x in cases),
        "no_answer": sum(x.category == "no_answer" for x in cases), "hard_negatives": sum(bool((x.metadata_json or {}).get("hard_negative")) for x in cases),
        "safety": sum(bool((x.metadata_json or {}).get("safety")) for x in cases),
        "alarm_fault": sum(x.category in {"fault_code_query", "fault_symptom"} for x in cases),
        "engineering_verified": sum(x.review_status == "engineering_verified" for x in cases),
        "expert_verified": sum(x.review_status == "expert_verified" for x in cases),
        "english_queries": sum(not any('\u4e00' <= char <= '\u9fff' for char in x.query_text) for x in cases)}
    checks = {"cases_gte_150": counts["cases"] >= 150, "vector_heavy_gte_30": counts["vector_heavy"] >= 30,
        "no_answer_gte_15": counts["no_answer"] >= 15, "hard_negative_gte_15": counts["hard_negatives"] >= 15,
        "safety_gte_15": counts["safety"] >= 15, "alarm_fault_gte_30": counts["alarm_fault"] >= 30,
        "all_engineering_verified": counts["engineering_verified"] == counts["cases"], "expert_verified_zero": counts["expert_verified"] == 0,
        "english_queries_zero": counts["english_queries"] == 0,
        "no_answer_expected_ids_empty": all(not (x.expected_document_ids or x.expected_chunk_ids) for x in cases if x.category == "no_answer")}
    result = {"generated_at": now_iso(), "status": "ENGINEERING_BENCHMARK_PASSED" if all(checks.values()) else "FAILED",
        "counts": counts, "checks": checks}
    write_json("chinese_engineering_benchmark_check.json", result); print(result)


if __name__ == "__main__": main()
