from __future__ import annotations

import argparse
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, RetrievalEvaluationResult, User
from app.schemas.retrieval_evaluation import RetrievalEvaluationRequest
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from generate_chinese_engineering_benchmark import DATASET
from task25b_r3_dev_common import now_iso, write_json


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--allow-real-api",action="store_true"); args=parser.parse_args()
    if not args.allow_real_api: raise SystemExit("explicit real API approval required")
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.role=="admin"))
        run=RetrievalEvaluationService(db).evaluate(RetrievalEvaluationRequest(
            name="Chinese development engineering Pilot quality",dataset_split="test",
            modes=["keyword","vector","hybrid","adaptive"],max_cases=150,dataset_version=DATASET),user)
        metrics=run.get("metrics_json") or {}; by_mode=metrics.get("by_mode") or {}; preferred=by_mode.get("adaptive") or {}
        result_rows = list(db.execute(select(RetrievalEvaluationResult, RetrievalEvaluationCase).join(
            RetrievalEvaluationCase, RetrievalEvaluationCase.id == RetrievalEvaluationResult.case_id).where(
            RetrievalEvaluationResult.run_id == run.get("id"), RetrievalEvaluationResult.retrieval_mode == "adaptive")))
        tp=fp=fn=0
        for result, case in result_rows:
            abstained = not (result.ranked_chunk_ids or result.ranked_document_ids or result.ranked_media_ids)
            actual = case.category == "no_answer"
            tp += int(actual and abstained); fp += int(not actual and abstained); fn += int(actual and not abstained)
        no_answer_f1 = (2*tp/(2*tp+fp+fn)) if (2*tp+fp+fn) else 0.0
        checks={"recall_at_5":preferred.get("recall_at_5",0)>=.80,"recall_at_10":preferred.get("recall_at_10",0)>=.90,
            "precision_at_5":preferred.get("precision_at_5",0)>=.45,"mrr":preferred.get("mrr",0)>=.75,
            "ndcg_at_10":preferred.get("ndcg_at_10",0)>=.80,"citation_validity":preferred.get("citation_valid",0)>=.98,
            "citation_coverage":preferred.get("citation_valid",0)>=.95,"model_accuracy":preferred.get("exact_model_accuracy")==1.0,
            "fault_alarm_accuracy":preferred.get("exact_fault_code_accuracy")==1.0,"no_answer_f1":no_answer_f1>=.85,
            "english_leakage":preferred.get("leakage",1)==0,"pending_leakage":preferred.get("leakage",1)==0,
            "p95":preferred.get("latency_p95_ms",999999)<=3500,"error_rate":metrics.get("error_rate",1)==0}
        payload={"generated_at":now_iso(),"result":"DEVELOPMENT_ENGINEERING_PILOT_PASS" if all(checks.values()) else "DEVELOPMENT_ENGINEERING_PILOT_FAIL",
            "run_id":str(run.get("id")),"dataset_version":DATASET,"cases":metrics.get("case_count"),"by_mode":by_mode,
            "preferred_mode":"adaptive","no_answer_f1":round(no_answer_f1,6),"checks":checks,"passed":all(checks.values()),"expert_validated":False}
    write_json("chinese_pilot_quality_gate.json",payload); print({"result":payload["result"],"checks":checks,"adaptive":preferred})


if __name__=="__main__": main()
