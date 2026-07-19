from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sqlalchemy import func, select, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import QARecord, User  # noqa: E402
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest  # noqa: E402
from app.services.candidate_hydration_service import CandidateHydrationService  # noqa: E402
from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService  # noqa: E402
from app.services.multi_query_retrieval_service import MultiQueryRetrievalService  # noqa: E402
from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService  # noqa: E402
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService  # noqa: E402
from app.services.query_signal_extraction_service import QuerySignalExtractionService  # noqa: E402
from app.services.result_set_refinement_service import ResultSetRefinementService  # noqa: E402
from app.services.rrf_fusion_service import RRFFusionService  # noqa: E402


DATASET = BACKEND_ROOT / "tests" / "fixtures" / "task27a_huawei_sun2000_engineering_candidate_v1.json"
EXPECTED_DATASET_HASH = "9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0"
BASELINE = PROJECT_ROOT / ".runtime" / "task27a" / "keyword_evaluation.json"
DEFAULT_OUTPUT = PROJECT_ROOT / ".runtime" / "task27a" / "r3_stage_diagnostics_pre.json"


def _snapshot(item: Any, *, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "chunk_id": item.chunk_id,
        "document_id": item.document_id,
        "document_title": item.document_title,
        "section_title": item.section_title,
        "source_type": getattr(item.document, "source_type", None),
        "source_channels": sorted(item.source_channels),
        "source_query_types": sorted(item.source_query_types),
        "raw_scores": dict(item.raw_scores),
        "rrf_score": round(float(item.rrf_score), 8),
        "final_score": round(float(item.final_score), 8),
        "direct_answer_score": round(float(item.direct_answer_score), 6),
        "direct_answer_level": item.direct_answer_level,
        "requested_information_coverage": round(float(item.requested_information_coverage), 6),
        "content_preview": " ".join(str(item.content or "").split())[:260],
    }


def _rank(values: list[dict[str, Any]], chunk_id: str) -> int | None:
    return next((item["rank"] for item in values if item["chunk_id"] == chunk_id), None)


def _field_matches(query: str, candidate: dict[str, Any] | None) -> dict[str, Any]:
    if candidate is None:
        return {"query_terms": [], "content": [], "section": [], "title": [], "phrase_coverage": 0.0}
    terms = QuerySignalExtractionService.retrieval_terms(query, limit=96)
    title = str(candidate.get("document_title") or "").casefold()
    section = str(candidate.get("section_title") or "").casefold()
    content = str(candidate.get("content_preview") or "").casefold()
    meaningful = [term for term in terms if len(term.strip()) >= 2]
    content_matches = [term for term in meaningful if term.casefold() in content]
    section_matches = [term for term in meaningful if term.casefold() in section]
    title_matches = [term for term in meaningful if term.casefold() in title]
    matched = set(content_matches + section_matches + title_matches)
    return {
        "query_terms": meaningful,
        "content": content_matches,
        "section": section_matches,
        "title": title_matches,
        "phrase_coverage": round(len(matched) / max(1, len(set(meaningful))), 6),
    }


def _diagnose_case(db, user: User, case: dict[str, Any]) -> dict[str, Any]:
    capture: dict[str, Any] = {"keyword_calls": []}
    lock = threading.Lock()
    expected_id = str(case["expected_chunk_ids"][0])

    original_hydrate = CandidateHydrationService.load_scope_candidates
    original_keyword = MultiQueryRetrievalService._keyword
    original_retrieve = MultiQueryRetrievalService.retrieve
    original_fuse = RRFFusionService.fuse
    original_guard = PreRerankHardGuardService.apply
    original_rerank = DeterministicEvidenceRerankService.rerank
    original_refine = ResultSetRefinementService.refine_query_aware

    def hydrate_wrapper(service, scope):
        result = original_hydrate(service, scope)
        chunk = result.chunks.get(expected_id)
        document = result.documents.get(str(chunk.document_id)) if chunk is not None else None
        capture["hydration"] = {
            "scope_row_count": len(result.rows),
            "expected_present": chunk is not None,
            "expected": None if chunk is None else {
                "chunk_id": expected_id,
                "document_id": str(chunk.document_id),
                "document_title": document.title if document else None,
                "section_title": chunk.section_title,
                "source_type": document.source_type if document else None,
                "content_preview": " ".join(str(chunk.content or "").split())[:260],
            },
            "sql_count": result.sql_count,
            "cache_hit": result.cache_hit,
        }
        return result

    def keyword_wrapper(service, channel, query, query_type, understanding, scope, top_k, *, hydrated_keyword_rows=None):
        result = original_keyword(
            service, channel, query, query_type, understanding, scope, top_k,
            hydrated_keyword_rows=hydrated_keyword_rows,
        )
        values = [_snapshot(item, rank=index) for index, item in enumerate(result, start=1)]
        with lock:
            capture["keyword_calls"].append({
                "channel": channel,
                "query_type": query_type,
                "query": query,
                "candidate_count": len(values),
                "expected_rank": _rank(values, expected_id),
                "candidates": values,
            })
        return result

    def retrieve_wrapper(service, *args, **kwargs):
        result = original_retrieve(service, *args, **kwargs)
        capture["multi_query_rankings"] = {
            key: [_snapshot(item, rank=index) for index, item in enumerate(values, start=1)]
            for key, values in result.rankings.items()
        }
        return result

    def fuse_wrapper(service, rankings, *args, **kwargs):
        result = original_fuse(service, rankings, *args, **kwargs)
        capture["fused"] = [_snapshot(item, rank=index) for index, item in enumerate(result, start=1)]
        return result

    def guard_wrapper(service, candidates, *args, **kwargs):
        result = original_guard(service, candidates, *args, **kwargs)
        capture["guard"] = {
            "candidates": [_snapshot(item, rank=index) for index, item in enumerate(result.candidates, start=1)],
            "diagnostics": result.diagnostics,
        }
        return result

    def rerank_wrapper(service, candidates, *args, **kwargs):
        result = original_rerank(service, candidates, *args, **kwargs)
        snapshots = [_snapshot(item, rank=index) for index, item in enumerate(result.candidates, start=1)]
        score_breakdown = result.diagnostics.get("score_breakdown", {})
        for snapshot in snapshots:
            snapshot["score_breakdown"] = score_breakdown.get(snapshot["chunk_id"])
        capture["rerank"] = {
            "candidates": snapshots,
            "diagnostics": result.diagnostics,
        }
        return result

    def refine_wrapper(service, raw, *args, **kwargs):
        result = original_refine(service, raw, *args, **kwargs)
        capture["final"] = {
            "candidates": [_snapshot(item, rank=index) for index, item in enumerate(result.surfaced, start=1)],
            "diagnostics": result.diagnostics,
        }
        return result

    with (
        patch.object(CandidateHydrationService, "load_scope_candidates", hydrate_wrapper),
        patch.object(MultiQueryRetrievalService, "_keyword", keyword_wrapper),
        patch.object(MultiQueryRetrievalService, "retrieve", retrieve_wrapper),
        patch.object(RRFFusionService, "fuse", fuse_wrapper),
        patch.object(PreRerankHardGuardService, "apply", guard_wrapper),
        patch.object(DeterministicEvidenceRerankService, "rerank", rerank_wrapper),
        patch.object(ResultSetRefinementService, "refine_query_aware", refine_wrapper),
    ):
        response = QueryAwareRetrievalService(db, current_user=user).search(QueryAwareSearchRequest(
            query=case["query"],
            request_id=f"task27a-r3-diagnostic-{case['case_id'].casefold()}",
            retrieval_mode="fast",
            top_k=5,
            enable_llm=False,
            allow_real_api=False,
            persist_result=False,
        ))

    initial_hits = sorted(
        (
            {"channel": item["channel"], "query_type": item["query_type"], "query": item["query"], "rank": item["expected_rank"]}
            for item in capture["keyword_calls"] if item["expected_rank"] is not None
        ),
        key=lambda item: item["rank"],
    )
    merged_values = [
        item
        for values in capture.get("multi_query_rankings", {}).values()
        for item in values
    ]
    fused = capture.get("fused", [])
    guarded = (capture.get("guard") or {}).get("candidates", [])
    reranked = (capture.get("rerank") or {}).get("candidates", [])
    final = (capture.get("final") or {}).get("candidates", [])
    answer_ids = [str(item.get("chunk_id")) for item in response.retrieved_chunks]
    reference_ids = [str(item.get("chunk_id")) for item in response.references]
    expected_rerank_breakdown = ((capture.get("rerank") or {}).get("diagnostics") or {}).get("score_breakdown", {}).get(expected_id)
    expected_snapshot = next((item for item in reranked if item["chunk_id"] == expected_id), None)
    if expected_snapshot is None:
        expected_snapshot = (capture.get("hydration") or {}).get("expected")
    removal = next((
        item for item in ((capture.get("guard") or {}).get("diagnostics") or {}).get("removals", [])
        if item.get("candidate_id") == expected_id
    ), None)

    if not (capture.get("hydration") or {}).get("expected_present"):
        eliminated = "NOT_IN_FORMAL_SCOPE"
    elif not initial_hits:
        eliminated = "NOT_RECALLED_BY_KEYWORD_VARIANTS"
    elif not any(item["chunk_id"] == expected_id for item in merged_values):
        eliminated = "CHANNEL_IDENTITY_BUDGET"
    elif _rank(fused, expected_id) is None:
        eliminated = "FUSION_LIMIT"
    elif _rank(guarded, expected_id) is None:
        eliminated = (removal or {}).get("reason") or "PRE_RERANK_GUARD"
    elif _rank(reranked, expected_id) is None:
        eliminated = "DETERMINISTIC_RERANK_BOUNDARY"
    elif _rank(final, expected_id) is None:
        eliminated = "PRESENTATION_TOP_K_OR_REFINEMENT"
    elif expected_id not in answer_ids:
        eliminated = "CITATION_OR_ANSWER_SELECTION"
    else:
        eliminated = None

    return {
        "case_id": case["case_id"],
        "query": case["query"],
        "expected_document_ids": case["expected_document_ids"],
        "expected_chunk_id": expected_id,
        "query_signals": response.query_signals,
        "scope": capture.get("hydration"),
        "initial_keyword": {
            "call_count": len(capture["keyword_calls"]),
            "expected_hits": initial_hits,
            "best_expected_rank": min((item["rank"] for item in initial_hits), default=None),
        },
        "multi_query_merged": {
            "expected_present": any(item["chunk_id"] == expected_id for item in merged_values),
            "best_expected_rank": min((item["rank"] for item in merged_values if item["chunk_id"] == expected_id), default=None),
        },
        "fused": {"expected_rank": _rank(fused, expected_id), "top_10": fused[:10]},
        "pre_rerank_guard": {
            "expected_rank": _rank(guarded, expected_id),
            "removal": removal,
        },
        "deterministic_rerank": {
            "expected_rank": _rank(reranked, expected_id),
            "expected_score_breakdown": expected_rerank_breakdown,
            "top_10": reranked[:10],
        },
        "field_and_phrase_matches": _field_matches(case["query"], expected_snapshot),
        "final_top_5": final,
        "final_expected_rank": _rank(final, expected_id),
        "answer_selected_chunk_ids": answer_ids,
        "reference_chunk_ids": reference_ids,
        "answer_selected_expected": expected_id in answer_ids,
        "reference_contains_expected": expected_id in reference_ids,
        "answer": response.answer,
        "eliminated_reason": eliminated,
        "stage_latency_ms": response.stage_latency,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only stage diagnostics for Task 27A-R3 failures")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evaluation", type=Path, default=BASELINE)
    parser.add_argument(
        "--selection",
        choices=("failed", "non_rank_one", "all"),
        default="failed",
    )
    args = parser.parse_args()

    dataset_hash = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    if dataset_hash != EXPECTED_DATASET_HASH:
        print(json.dumps({
            "status": "DATASET_INTEGRITY_FAILURE",
            "expected_sha256": EXPECTED_DATASET_HASH,
            "actual_sha256": dataset_hash,
        }, indent=2))
        return 2
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
    if args.selection == "failed":
        selected_ids = {item["case_id"] for item in evaluation["cases"] if not item["passed"]}
    elif args.selection == "non_rank_one":
        selected_ids = set()
        for item in evaluation["cases"]:
            expected = set(item["expected"]["chunk_ids"])
            ranked = list(item["actual"]["chunk_ids"])
            if expected and (not ranked or ranked[0] not in expected):
                selected_ids.add(item["case_id"])
    else:
        selected_ids = {item["case_id"] for item in evaluation["cases"]}
    cases = [item for item in dataset["cases"] if item["case_id"] in selected_ids]

    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        user = db.scalar(select(User).where(User.username == "admin"))
        if user is None:
            raise RuntimeError("admin user is required for read-only service diagnostics")
        qa_before = int(db.scalar(select(func.count()).select_from(QARecord)) or 0)
        diagnostics = [_diagnose_case(db, user, case) for case in cases]
        qa_after = int(db.scalar(select(func.count()).select_from(QARecord)) or 0)
        db.rollback()

    output = {
        "status": "COMPLETE",
        "mode": "keyword_only_read_only",
        "database_name": engine.url.database,
        "dataset": {
            "dataset_id": dataset["dataset_id"],
            "sha256": dataset_hash,
            "failed_case_count": len(cases),
            "selection": args.selection,
            "evaluation": str(args.evaluation),
        },
        "qa_count_before": qa_before,
        "qa_count_after": qa_after,
        "production_database_unchanged": qa_before == qa_after,
        "cases": diagnostics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": output["status"],
        "output": str(args.output),
        "dataset_sha256": dataset_hash,
        "case_count": len(cases),
        "qa_count_before": qa_before,
        "qa_count_after": qa_after,
        "stage_summary": [{
            "case_id": item["case_id"],
            "initial_rank": item["initial_keyword"]["best_expected_rank"],
            "fused_rank": item["fused"]["expected_rank"],
            "rerank_rank": item["deterministic_rerank"]["expected_rank"],
            "final_rank": item["final_expected_rank"],
            "answer_selected": item["answer_selected_expected"],
            "eliminated_reason": item["eliminated_reason"],
        } for item in diagnostics],
    }, ensure_ascii=False, indent=2))
    return 0 if qa_before == qa_after else 2


if __name__ == "__main__":
    raise SystemExit(main())
