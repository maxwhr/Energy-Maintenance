from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, RetrievalEvaluationCase
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from check_task25b_r3_dev_r3_canary import DATASET, _run_mode, _take
from task25b_r3_dev_r3_common import OUT, now_iso


MODES = ("keyword", "raw_vector_pilot_r2", "semantic_vector_pilot_r3", "adaptive_semantic")


def selected_cases(db) -> list[RetrievalEvaluationCase]:
    pool = list(db.scalars(select(RetrievalEvaluationCase).where(
        RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
        RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
    ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name)))
    selected = []
    _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")) and "safety" in (((case.metadata_json or {}).get("grounding_evidence") or {}).get("themes") or []), 3, selected)
    _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")) and "communication" in (((case.metadata_json or {}).get("grounding_evidence") or {}).get("themes") or []), 3, selected)
    _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")), 6, selected)
    _take(pool, lambda case: bool((case.metadata_json or {}).get("is_model_case")), 4, selected)
    _take(pool, lambda case: bool((case.metadata_json or {}).get("is_alarm_case")), 4, selected)
    _take(pool, lambda case: bool((case.metadata_json or {}).get("is_no_answer")), 4, selected)
    _take(pool, lambda case: not bool((case.metadata_json or {}).get("is_no_answer")), 6, selected)
    if len(selected) != 30:
        raise RuntimeError(f"Canary stratification incomplete: {len(selected)}/30")
    return selected


def worker(mode: str, case_id: str) -> dict:
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        case = db.get(RetrievalEvaluationCase, case_id)
        _run_mode(mode=mode, cases=[case], db=db, scope=scope, chunks={}, documents={}, warm=False)
        return _run_mode(mode=mode, cases=[case], db=db, scope=scope, chunks={}, documents={}, warm=True)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--offset", type=int, required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if not args.allow_real_api or not 0 <= args.offset < 30 or not 1 <= args.limit <= 8:
        raise SystemExit("explicit real API batch limits are required")
    with SessionLocal() as db:
        cases = selected_cases(db)[args.offset:args.offset + args.limit]
        allowed = set(RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True).allowed_document_ids)
    with ThreadPoolExecutor(max_workers=min(4, len(cases))) as pool:
        rows = list(pool.map(lambda case: worker(args.mode, str(case.id)), cases))
    ranked_ids = {value for row in rows for value in row["ranked_ids"]}
    with SessionLocal() as db:
        chunk_docs = {str(chunk.id): chunk.document_id for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ranked_ids)))} if ranked_ids else {}
    for row in rows:
        row["leakage"] = any(chunk_docs.get(chunk_id) not in allowed for chunk_id in row["ranked_ids"])
    batch_dir = OUT / "canary_batches"; batch_dir.mkdir(parents=True, exist_ok=True)
    path = batch_dir / f"{args.mode}_{args.offset:02d}.json"
    path.write_text(json.dumps({"generated_at": now_iso(), "mode": args.mode, "offset": args.offset, "rows": rows, "warm": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({"status": "PASSED", "mode": args.mode, "offset": args.offset, "count": len(rows)})


if __name__ == "__main__":
    main()
