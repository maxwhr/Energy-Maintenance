from __future__ import annotations

import argparse
import json

from sqlalchemy import func, select

from task25b_r2_u3_common import RUNTIME, now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeDocument, RetrievalEvaluationCase


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-after-document-approval", action="store_true")
    parser.add_argument("--resume-after-benchmark-review", action="store_true")
    parser.add_argument("--resume-pilot-index", action="store_true")
    args = parser.parse_args()
    corpus = json.loads((RUNTIME / "u3_corpus_gate.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        pending_docs = int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.manufacturer == "huawei",
            KnowledgeDocument.source_type.in_(["vendor_official", "vendor_official_html"]),
            KnowledgeDocument.review_status == "pending_review",
        )) or 0)
        cases = list(db.scalars(select(RetrievalEvaluationCase)))
    expert = sum(item.review_status == "expert_verified" for item in cases)
    second = sum(bool((item.metadata_json or {}).get("second_reviews")) for item in cases)
    vector_heavy = sum(item.review_status == "expert_verified" and bool((item.metadata_json or {}).get("vector_heavy")) for item in cases)
    no_answer = sum(item.review_status == "expert_verified" and item.category == "no_answer" for item in cases)
    if pending_docs or not args.resume_after_document_approval:
        status = "AWAITING_HUMAN_DOCUMENT_APPROVAL"
    elif corpus.get("status") != "CORPUS_READY":
        status = "BLOCKED_CORPUS_GATE"
    elif expert < 100 or second < 20 or vector_heavy < 20 or no_answer < 15 or not args.resume_after_benchmark_review:
        status = "AWAITING_HUMAN_BENCHMARK_REVIEW"
    elif not args.resume_pilot_index:
        status = "READY_FOR_EXPLICIT_PILOT_RESUME"
    else:
        status = "PILOT_RESUME_PRECONDITIONS_MET"
    payload = {
        "generated_at": now_iso(), "status": status, "pending_documents": pending_docs,
        "corpus_status": corpus.get("status"), "expert_verified": expert, "second_reviewed": second,
        "vector_heavy_verified": vector_heavy, "no_answer_verified": no_answer,
        "document_review_url": "http://127.0.0.1:8012/review",
        "benchmark_review_url": "http://127.0.0.1:8012/system/retrieval-quality",
        "pilot_index_allowed": status == "PILOT_RESUME_PRECONDITIONS_MET",
        "automatic_approval": False, "automatic_expert_verification": False,
    }
    write_json("u3_resume_gate.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["pilot_index_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
