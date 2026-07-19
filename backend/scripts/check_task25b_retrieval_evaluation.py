from __future__ import annotations

import argparse
from sqlalchemy import select

from task25b_common import write_result
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, RetrievalEvaluationRun, User
from app.schemas.retrieval_evaluation import RetrievalEvaluationRequest
from app.services.retrieval_evaluation_service import RetrievalEvaluationService, RetrievalEvaluationServiceError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--max-cases", type=int, default=100)
    args = parser.parse_args()
    with SessionLocal() as db:
        counts = {split: len(list(db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.dataset_split == split)))) for split in ("train", "dev", "test")}
        verified = len(list(db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.review_status.in_(["engineering_verified", "expert_verified"])))))
        if args.latest:
            latest = db.scalar(select(RetrievalEvaluationRun).order_by(RetrievalEvaluationRun.created_at.desc()))
            if latest:
                metrics = latest.metrics_json or {}
                result = {"status": "PASSED" if metrics.get("threshold_result", {}).get("passed") else "FAILED",
                          "run_id": str(latest.id), "run_status": latest.run_status, "dataset_version": latest.dataset_version,
                          "metrics": metrics, "controlled_cases": sum(counts.values()), "verified_cases": verified}
            else:
                result = {"status": "BLOCKED_DATA", "reason": "no evaluation run found", "counts": counts}
        elif not args.execute:
            result = {"status": "DRY_RUN", "counts": counts, "verified_cases": verified, "external_api_called": False}
        else:
            user = db.scalar(select(User).where(User.role.in_(["admin", "expert"])))
            try:
                run = RetrievalEvaluationService(db).evaluate(RetrievalEvaluationRequest(max_cases=args.max_cases), user)
                metrics = run.get("metrics_json") or {}
                result = {"status": "PASSED" if metrics.get("threshold_result", {}).get("passed") else "FAILED",
                          "run_id": str(run.get("id")), "run_status": run.get("run_status"),
                          "dataset_version": run.get("dataset_version"), "metrics": metrics,
                          "controlled_cases": sum(counts.values()), "verified_cases": verified}
            except RetrievalEvaluationServiceError as exc:
                result = {"status": "BLOCKED_DATA", "reason": str(exc), "counts": counts}
    write_result("retrieval_evaluation.json", result)
    return 0 if result["status"] in {"PASSED", "DRY_RUN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
