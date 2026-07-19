from __future__ import annotations

import argparse
from types import SimpleNamespace

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.services.evidence_aware_rerank_service import EvidenceAwareRerankService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.rrf_fusion_service import QueryAwareCandidate
from task25b_r3_dev_r5_r1_common import now_iso, sha256_text, write_json


def candidate(candidate_id: str, content: str, rank: int, *, model: str = "") -> QueryAwareCandidate:
    return QueryAwareCandidate(
        candidate_id=candidate_id,
        chunk_id=candidate_id,
        document_id=f"doc-{candidate_id}",
        document_title=f"Huawei {model or 'manual'}",
        content=content,
        section_title="故障处理",
        page_number=rank,
        chunk=SimpleNamespace(id=candidate_id, metadata_json={}),
        document=SimpleNamespace(id=f"doc-{candidate_id}", model=model, metadata_json={}),
        source_channels={"SCOPED_KEYWORD"},
        source_query_types={"ORIGINAL"},
        raw_ranks={"SCOPED_KEYWORD:ORIGINAL": rank},
        rrf_score=round(1 / (60 + rank), 8),
        final_score=round(1 / (60 + rank), 8),
        source_chunk_ids=[candidate_id],
        scope_validation_passed=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--case", choices=["similar_candidates", "model_mismatch", "symptom_action_conflict"])
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("real rerank probe requires explicit real API enablement")

    cases = [
        (
            "similar_candidates",
            "通信频繁中断，先检查什么？",
            [
                candidate("c1", "检查 RS485 线缆连接和端子是否松动。", 1),
                candidate("c2", "检查通信线缆、端子和波特率配置。", 2),
            ],
        ),
        (
            "model_mismatch",
            "SUN2000-100KTL-M1 通信异常如何检查？",
            [
                candidate("c3", "SUN2000-100KTL-M1 通信异常时检查 RS485 连接。", 1, model="SUN2000-100KTL-M1"),
                candidate("c4", "SUN2000-50KTL-M3 通信参数设置说明。", 2, model="SUN2000-50KTL-M3"),
            ],
        ),
        (
            "symptom_action_conflict",
            "设备离线且指示灯正常，应先做什么？",
            [
                candidate("c5", "设备离线但指示灯正常时，检查管理系统网络连接。", 1),
                candidate("c6", "更换风扇前必须断电并等待放电完成。", 2),
                candidate("c7", "确认通信恢复后观察设备在线状态。", 3),
            ],
        ),
    ]
    if args.case:
        cases = [item for item in cases if item[0] == args.case]
    rows = []
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("rerank probe actor missing")
        signals_service = QuerySignalExtractionService()
        completeness = QuestionCompletenessService()
        for name, query, candidates in cases:
            signals = signals_service.extract(query)
            understanding = LLMQueryUnderstandingService._deterministic(signals, completeness.assess(signals))
            before = [item.candidate_id for item in candidates]
            result = EvidenceAwareRerankService(db, current_user=user).rerank(
                candidates,
                understanding=understanding,
                allow_real_api=True,
                force=True,
            )
            after = [item.candidate_id for item in result.candidates]
            rows.append({
                "case": name,
                "query_hash": sha256_text(query),
                "model_called": result.diagnostics.get("rerank_model_called"),
                "structured_success": result.diagnostics.get("rerank_structured_success"),
                "parse_strategy": result.diagnostics.get("rerank_parse_strategy"),
                "fallback": result.fallback,
                "fallback_stage": result.diagnostics.get("rerank_fallback_stage"),
                "fallback_reason": result.diagnostics.get("rerank_fallback_reason"),
                "trace_id": result.diagnostics.get("rerank_trace_id"),
                "latency_ms": result.diagnostics.get("latency_ms"),
                "response_format_mode": result.diagnostics.get("response_format_mode"),
                "provider_status": result.diagnostics.get("provider_status"),
                "validation_errors": result.diagnostics.get("validation_errors") or [],
                "raw_text_length": result.diagnostics.get("raw_text_length"),
                "raw_top_level_type": result.diagnostics.get("raw_top_level_type"),
                "raw_shape": result.diagnostics.get("raw_shape") or {},
                "response_field_names": result.diagnostics.get("response_field_names") or [],
                "provider_response_meta": result.diagnostics.get("provider_response_meta") or {},
                "candidate_count_in": len(before),
                "candidate_count_out": len(after),
                "candidate_additions": result.candidate_additions,
                "candidate_source_modifications": result.candidate_source_modifications,
                "candidate_set_preserved": set(before) == set(after) and len(before) == len(after),
                "order_legal": all(value in before for value in after),
            })

    fallback_candidates = [
        candidate("f1", "通信检查说明。", 1),
        candidate("f2", "通信恢复验证。", 2),
    ]
    fallback_understanding = LLMQueryUnderstandingService._deterministic(
        QuerySignalExtractionService().extract("通信中断怎么处理"),
        QuestionCompletenessService().assess(QuerySignalExtractionService().extract("通信中断怎么处理")),
    )
    original_order = [item.candidate_id for item in fallback_candidates]
    fallback = EvidenceAwareRerankService(None, model_call=lambda _: "not-json").rerank(
        fallback_candidates,
        understanding=fallback_understanding,
        allow_real_api=True,
        force=True,
    )
    fallback_order_preserved = [item.candidate_id for item in fallback.candidates] == original_order

    success_count = sum(bool(row["structured_success"]) for row in rows)
    passed = (
        success_count == len(rows)
        and all(row["model_called"] and not row["fallback"] and row["candidate_set_preserved"] and row["order_legal"] for row in rows)
        and all(float(row["latency_ms"] or 0) > 100 for row in rows)
        and fallback.fallback
        and fallback_order_preserved
    )
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "provider": "cloud_openai",
        "model": settings.CLOUD_LLM_MODEL,
        "cases": len(rows),
        "structured_success": success_count,
        "rows": rows,
        "fallback_order_preserved": fallback_order_preserved,
    }
    write_json("rerank_probe.json", payload)
    print(payload)
    if not passed:
        raise SystemExit("RERANK_PROBE_FAILED: full Canary remains blocked")


if __name__ == "__main__":
    main()
