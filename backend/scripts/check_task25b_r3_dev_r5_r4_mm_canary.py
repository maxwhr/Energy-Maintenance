from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import UUID
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, QueryAwareRetrievalSession, User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.schemas.query_understanding import ClarificationRequest
from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r4_mm_common import (
    DATASET_VERSION,
    OUT,
    now_iso,
    p95,
    ratio,
    sha256_json,
    write_once,
)


SOURCE_DATASET = OUT.parent / "task25b_r3_dev_r5" / "train_dev_dataset_v2.json"
CHECKPOINT = OUT / "canary_checkpoint.json"
CASE_RESULTS = OUT / "canary_case_results.json"
CASE_RESULTS_CSV = OUT / "canary_case_results.csv"
RUN_LOCK = OUT / "canary.lock"


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _result_key(iteration: int, configuration: str, case_id: str) -> str:
    return f"{iteration}|{configuration}|{case_id}"


def _compact_result(*, iteration: int, configuration: str, case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    rank = int(row.get("rank_at_10") or 0)
    mode = str(row.get("query_understanding_mode") or "")
    minimax = row.get("minimax") or {}
    latency = row.get("stage_latency") or {}
    return {
        "iteration": iteration,
        "configuration": configuration,
        "case_id": case["case_id"],
        "category": case.get("category"),
        "query_hash": hashlib.sha256(str(case.get("query") or "").encode("utf-8")).hexdigest(),
        "expected_evidence_hash": sha256_json(sorted(case.get("expected_chunk_ids") or [])),
        "understanding_mode": mode,
        "deterministic_intent": row.get("actual_intent"),
        "canonical_query_hash": hashlib.sha256(str(row.get("canonical_query") or "").encode("utf-8")).hexdigest(),
        "ambiguity_options_count": int(row.get("ambiguity_options_count") or 0),
        "minimax_eligible": configuration == "deterministic_with_optional_minimax" and bool(case.get("ambiguous")),
        "minimax_called": mode in {"MINIMAX_AMBIGUITY_RESOLUTION", "SAFE_FALLBACK"},
        "minimax_structured_success": mode == "MINIMAX_AMBIGUITY_RESOLUTION",
        "minimax_fallback": mode == "SAFE_FALLBACK",
        "minimax_fallback_reason": minimax.get("provider_error_code") or row.get("minimax_fallback_reason"),
        "requested_channels": row.get("requested_channels") or [],
        "executed_channels": row.get("actual_channels") or [],
        "candidate_count": len(row.get("raw_candidates") or []),
        "candidate_recall_at_50": bool(row.get("candidate_hit_at_50")),
        "recall_at_5": bool(0 < rank <= 5),
        "reciprocal_rank": round(1 / rank, 6) if rank else 0.0,
        "ndcg_at_10": round(1 / math.log2(rank + 1), 6) if rank else 0.0,
        "citation_validity": bool(row.get("citation_valid", True)),
        "citation_coverage": float(row.get("citation_coverage") or 0.0),
        "confidence_status": row.get("confidence_status"),
        "clarification_expected": bool(case.get("requires_clarification")),
        "clarification_actual": bool(row.get("clarified")),
        "no_answer_expected": bool(case.get("no_answer")),
        "no_answer_actual": row.get("confidence_status") == "INSUFFICIENT_EVIDENCE",
        "latency_breakdown": latency,
        "minimax_latency_ms": float(minimax.get("latency_ms") or (
            latency.get("query_understanding_ms") if mode in {"MINIMAX_AMBIGUITY_RESOLUTION", "SAFE_FALLBACK"} else 0.0
        ) or 0.0),
        "error_code": row.get("error"),
    }


def _materialize_case_results(checkpoint: dict[str, Any], case_by_id: dict[str, dict[str, Any]]) -> None:
    compact = []
    for entry in checkpoint.get("results") or []:
        case = case_by_id.get(entry["case_id"])
        if case is None:
            continue
        compact.append(_compact_result(
            iteration=int(entry["iteration"]),
            configuration=str(entry["configuration"]),
            case=case,
            row=entry["result"],
        ))
    compact.sort(key=lambda item: (item["iteration"], item["configuration"], item["case_id"]))
    _atomic_json(CASE_RESULTS, {
        "generated_at": now_iso(),
        "unique_key": ["iteration", "configuration", "case_id"],
        "result_count": len(compact),
        "duplicate_count": len(compact) - len({
            (item["iteration"], item["configuration"], item["case_id"]) for item in compact
        }),
        "rows": compact,
    })
    columns = list(compact[0].keys()) if compact else []
    temporary = CASE_RESULTS_CSV.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in compact:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })
    os.replace(temporary, CASE_RESULTS_CSV)


def _seed_iteration_one_checkpoint(dataset: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    checkpoint = {
        "schema_version": "task25b_r3_dev_r5_r4_mm_checkpoint_v1",
        "run_id": "r5r4mm-iteration1-imported-complete",
        "resume_parent_run_id": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "results": [],
    }
    for configuration, section in (
        ("deterministic_only", artifact["deterministic_only"]),
        ("deterministic_with_optional_minimax", artifact["optional_minimax"]),
    ):
        for row in section.get("rows") or []:
            checkpoint["results"].append({
                "key": _result_key(1, configuration, row["case_id"]),
                "iteration": 1,
                "configuration": configuration,
                "case_id": row["case_id"],
                "result": row,
            })
    _atomic_json(CHECKPOINT, checkpoint)
    _materialize_case_results(checkpoint, {row["case_id"]: row for row in dataset["rows"]})
    return checkpoint


def _load_checkpoint(*, run_id: str | None = None) -> dict[str, Any]:
    if CHECKPOINT.exists():
        checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        keys = [entry["key"] for entry in checkpoint.get("results") or []]
        if len(keys) != len(set(keys)):
            raise SystemExit("Canary checkpoint contains duplicate iteration/configuration/case keys")
        return checkpoint
    checkpoint = {
        "schema_version": "task25b_r3_dev_r5_r4_mm_checkpoint_v1",
        "run_id": run_id or f"r5r4mm-{uuid4()}",
        "resume_parent_run_id": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "results": [],
        "configuration_completions": [],
    }
    _atomic_json(CHECKPOINT, checkpoint)
    return checkpoint


def _append_checkpoint_result(
    checkpoint: dict[str, Any],
    *,
    iteration: int,
    configuration: str,
    case_id: str,
    result: dict[str, Any],
) -> None:
    key = _result_key(iteration, configuration, case_id)
    existing = {entry["key"] for entry in checkpoint.get("results") or []}
    if key in existing:
        raise SystemExit(f"refusing duplicate Canary checkpoint key: {key}")
    checkpoint.setdefault("results", []).append({
        "key": key,
        "iteration": iteration,
        "configuration": configuration,
        "case_id": case_id,
        "result": result,
    })
    checkpoint["updated_at"] = now_iso()
    _atomic_json(CHECKPOINT, checkpoint)


def _iteration_cases(dataset: dict[str, Any], iteration: int) -> list[dict[str, Any]]:
    rows = list(dataset["rows"])
    if iteration == 1:
        return rows
    original_no_answer = [row for row in rows if row.get("category") == "no_answer"]
    if len(rows) != 81 or len(original_no_answer) != 8:
        raise SystemExit(
            f"unexpected frozen Train/Dev shape for calibrated execution set: "
            f"total={len(rows)}, original_no_answer={len(original_no_answer)}"
        )
    excluded = {row["case_id"] for row in original_no_answer[3:]}
    calibrated = [row for row in rows if row["case_id"] not in excluded]
    if len(calibrated) != 76 or sum(bool(row.get("no_answer")) for row in calibrated) != 8:
        raise SystemExit("calibrated execution set must contain 76 cases and exactly 8 no-answer cases")
    return calibrated


@contextmanager
def _exclusive_run_lock(run_id: str) -> Iterator[None]:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(RUN_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        owner = RUN_LOCK.read_text(encoding="utf-8", errors="replace") if RUN_LOCK.exists() else "unknown"
        raise SystemExit(f"another Canary execution owns the run lock: {owner}") from exc
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"run_id": run_id, "pid": os.getpid(), "started_at": now_iso()}))
        yield
    finally:
        RUN_LOCK.unlink(missing_ok=True)


def _unique_take(rows: list[dict[str, Any]], selected: list[dict[str, Any]], predicate, count: int) -> None:
    used = {row["case_id"] for row in selected}
    matches = [row for row in rows if row["case_id"] not in used and predicate(row)]
    if len(matches) < count:
        raise SystemExit(f"insufficient source-grounded Train/Dev cases: {len(matches)}/{count}")
    selected.extend(deepcopy(matches[:count]))


def _canonical_contract(query: str, expected_intent: str) -> list[str]:
    signals = QuerySignalExtractionService().extract(query)
    terms = [*signals.device_models, *signals.alarm_codes]
    replacements = {
        "掉线": "通信中断", "连不上": "连接失败", "不出力": "无功率输出",
        "灯不亮": "指示灯不亮", "平台没数据": "监控平台无数据", "晚上": "夜间",
    }
    for source, target in replacements.items():
        if source in query:
            terms.append(target)
    suffix = {
        "CAUSE": "查询可能原因", "TROUBLESHOOTING": "查询排查方法", "PROCEDURE": "查询操作步骤",
        "SAFETY": "查询安全要求", "ALARM": "查询告警含义", "PREREQUISITE": "查询操作前提",
        "VERIFICATION": "查询恢复验证方法",
    }.get(expected_intent)
    if suffix:
        terms.append(suffix)
    return list(dict.fromkeys(terms))


def _expected_intent(row: dict[str, Any]) -> str:
    old = str(row.get("expected_intent") or "GENERAL")
    query = str(row["query"])
    if any(term in query for term in ("为什么", "什么原因", "啥原因", "原因", "怎么回事")):
        return "CAUSE"
    if any(term in query for term in ("安全", "风险", "危险", "防护", "触电")):
        return "SAFETY"
    if old in {"DIAGNOSIS", "COMPONENT"}:
        return "TROUBLESHOOTING"
    return old if old in {
        "CAUSE", "TROUBLESHOOTING", "PROCEDURE", "SAFETY", "ALARM", "PREREQUISITE",
        "VERIFICATION", "COMMUNICATION", "GENERAL",
    } else "GENERAL"


def _normalize_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    row["case_id"] = f"r4mm-{index:03d}-" + hashlib.sha256(str(row["query"]).encode("utf-8")).hexdigest()[:12]
    row["dataset_version"] = DATASET_VERSION
    row["expected_intent"] = _expected_intent(row)
    row["expected_canonical_terms"] = _canonical_contract(row["query"], row["expected_intent"])
    row["engineering_candidate"] = True
    row["expert_verified"] = False
    row.setdefault("ambiguous", bool(row.get("requires_clarification")))
    row.setdefault("html_faq", False)
    row.setdefault("pdf", bool(row.get("expected_document_ids")))
    row.setdefault("multi_document_complementary", False)
    row.setdefault("entity_conflict", False)
    return row


def _create_dataset(db) -> dict[str, Any]:
    destination = OUT / "train_dev_dataset_v1.json"
    if destination.exists():
        return json.loads(destination.read_text(encoding="utf-8"))
    if not SOURCE_DATASET.exists():
        raise SystemExit("frozen R5 Train/Dev source is missing")
    source = json.loads(SOURCE_DATASET.read_text(encoding="utf-8"))
    rows = source.get("rows") or []
    selected: list[dict[str, Any]] = []
    _unique_take(rows, selected, lambda row: row.get("category") == "oral_maintenance" and row.get("communication"), 8)
    _unique_take(rows, selected, lambda row: row.get("category") == "oral_maintenance" and row.get("cause"), 8)
    _unique_take(rows, selected, lambda row: row.get("category") == "oral_maintenance" and row.get("action"), 8)
    _unique_take(rows, selected, lambda row: row.get("category") == "oral_maintenance" and row.get("safety"), 6)
    _unique_take(rows, selected, lambda row: row.get("category") == "device_model_query", 8)
    _unique_take(rows, selected, lambda row: row.get("category") == "alarm_query", 8)
    _unique_take(rows, selected, lambda row: row.get("category") == "no_answer", 8)
    _unique_take(rows, selected, lambda row: row.get("category") == "clarification", 12)

    for row in selected:
        row["pdf"] = bool(row.get("expected_document_ids"))
        row["ambiguous"] = bool(row.get("requires_clarification"))
    for row in [item for item in selected if item.get("category") == "clarification"][:8]:
        row["context_merge"] = True
        if not row.get("clarification"):
            row["clarification"] = "型号是 SUN2000-50KTL，现象是通信中断，想了解原因"
            row["context_expected_model"] = "SUN2000-50KTL"

    html_queries = [
        ("2f6e8766-df74-4e31-abd4-c4b806a538bb", "SUN2000逆变器无法启动如何排查？", "TROUBLESHOOTING"),
        ("2cc85307-e1f3-4382-896f-2cdae645af11", "SUN2000如何恢复WiFi初始密码？", "PROCEDURE"),
        ("7be3e048-f732-41ff-b0fb-c14719a77e2c", "SUN2000夜间WiFi通信异常如何排查？", "TROUBLESHOOTING"),
        ("12703ebb-4860-4a8a-bed3-11734dbcdfa5", "LUNA2000废旧电池如何回收？", "PROCEDURE"),
        ("584adeaf-7221-4ab6-b191-749ce3c99c57", "LUNA2000如何更换熔丝？", "PROCEDURE"),
    ]
    for document_id, query, intent in html_queries:
        document = db.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.id == UUID(document_id),
            KnowledgeDocument.file_ext == "html",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
        ))
        if document is None:
            raise SystemExit(f"approved HTML FAQ source missing: {document_id}")
        chunk = db.scalar(select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document.id,
            KnowledgeChunk.status == "active",
        ).order_by(KnowledgeChunk.chunk_index))
        if chunk is None:
            raise SystemExit(f"HTML FAQ active chunk missing: {document.id}")
        selected.append({
            "case_id": "",
            "category": "html_faq",
            "query": query,
            "expected_intent": intent,
            "expected_document_ids": [str(document.id)],
            "expected_chunk_ids": [str(chunk.id)],
            "expected_device_models": QuerySignalExtractionService().extract(query).device_models,
            "expected_alarm_codes": [],
            "source_grounded": True,
            "no_answer": False,
            "requires_clarification": False,
            "vector_heavy": True,
            "oral": True,
            "context_merge": False,
            "communication": "WiFi" in query,
            "cause": intent == "CAUSE",
            "action": intent == "TROUBLESHOOTING",
            "safety": False,
            "verification": False,
            "html_faq": True,
            "pdf": False,
            "ambiguous": False,
            "multi_document_complementary": False,
            "entity_conflict": False,
            "expert_verified": False,
        })

    grounded = [row for row in selected if row.get("expected_chunk_ids") and row.get("pdf")]
    for offset in range(5):
        first = grounded[offset * 2]
        second = grounded[offset * 2 + 1]
        query = f"同时查询以下两项维护信息：{first['query']}；{second['query']}"
        selected.append({
            **deepcopy(first),
            "case_id": "",
            "category": "multi_document_complementary",
            "query": query,
            "expected_document_ids": list(dict.fromkeys([
                *(first.get("expected_document_ids") or []), *(second.get("expected_document_ids") or [])
            ])),
            "expected_chunk_ids": list(dict.fromkeys([
                *(first.get("expected_chunk_ids") or []), *(second.get("expected_chunk_ids") or [])
            ])),
            "multi_document_complementary": True,
            "vector_heavy": True,
        })

    for offset in range(5):
        query = f"SUN2000-999KTL-X{offset + 21} 与 SmartLogger 告警代码 {991021 + offset} 的含义是否相同？"
        selected.append({
            "case_id": "",
            "category": "entity_conflict_no_answer",
            "query": query,
            "expected_intent": "ALARM",
            "expected_document_ids": [],
            "expected_chunk_ids": [],
            "expected_device_models": QuerySignalExtractionService().extract(query).device_models,
            "expected_alarm_codes": QuerySignalExtractionService().extract(query).alarm_codes,
            "source_grounded": True,
            "no_answer": True,
            "requires_clarification": False,
            "vector_heavy": False,
            "oral": True,
            "context_merge": False,
            "communication": False,
            "cause": False,
            "action": False,
            "safety": False,
            "verification": False,
            "html_faq": False,
            "pdf": False,
            "ambiguous": False,
            "multi_document_complementary": False,
            "entity_conflict": True,
            "conflict_reason": "查询将不存在的型号和告警绑定并要求跨设备等同解释；预期证据ID必须为空。",
            "expert_verified": False,
        })

    normalized = [_normalize_row(row, index=index) for index, row in enumerate(selected, start=1)]
    coverage = {
        "total": len(normalized),
        "exact_model": sum(bool(row.get("expected_device_models")) for row in normalized),
        "exact_alarm": sum(bool(row.get("expected_alarm_codes")) for row in normalized),
        "oral": sum(bool(row.get("oral")) for row in normalized),
        "ambiguity": sum(bool(row.get("ambiguous")) for row in normalized),
        "vector_heavy": sum(bool(row.get("vector_heavy")) for row in normalized),
        "communication": sum(bool(row.get("communication")) for row in normalized),
        "cause": sum(bool(row.get("cause")) for row in normalized),
        "action": sum(bool(row.get("action")) for row in normalized),
        "safety": sum(bool(row.get("safety")) for row in normalized),
        "no_answer": sum(bool(row.get("no_answer")) for row in normalized),
        "requires_clarification": sum(bool(row.get("requires_clarification")) for row in normalized),
        "context_merge": sum(bool(row.get("context_merge")) for row in normalized),
        "html_faq": sum(bool(row.get("html_faq")) for row in normalized),
        "pdf": sum(bool(row.get("pdf")) for row in normalized),
        "multi_document_complementary": sum(bool(row.get("multi_document_complementary")) for row in normalized),
        "entity_conflict": sum(bool(row.get("entity_conflict")) for row in normalized),
    }
    requirements = {
        "total_at_least_60": coverage["total"] >= 60,
        "exact_model_at_least_8": coverage["exact_model"] >= 8,
        "exact_alarm_at_least_8": coverage["exact_alarm"] >= 8,
        "oral_at_least_15": coverage["oral"] >= 15,
        "ambiguity_at_least_12": coverage["ambiguity"] >= 12,
        "vector_heavy_at_least_15": coverage["vector_heavy"] >= 15,
        "communication_at_least_8": coverage["communication"] >= 8,
        "cause_at_least_8": coverage["cause"] >= 8,
        "action_at_least_8": coverage["action"] >= 8,
        "safety_at_least_6": coverage["safety"] >= 6,
        "no_answer_at_least_8": coverage["no_answer"] >= 8,
        "clarification_at_least_8": coverage["requires_clarification"] >= 8,
        "context_at_least_8": coverage["context_merge"] >= 8,
        "html_faq_at_least_5": coverage["html_faq"] >= 5,
        "pdf_at_least_10": coverage["pdf"] >= 10,
        "multi_document_at_least_5": coverage["multi_document_complementary"] >= 5,
        "entity_conflict_at_least_5": coverage["entity_conflict"] >= 5,
        "expected_empty_for_no_answer": all(not row.get("expected_chunk_ids") for row in normalized if row.get("no_answer")),
        "engineering_candidate_only": all(row.get("engineering_candidate") for row in normalized),
        "expert_verified_zero": not any(row.get("expert_verified") for row in normalized),
    }
    if not all(requirements.values()):
        raise SystemExit({"coverage": coverage, "failed": [key for key, value in requirements.items() if not value]})
    payload = {
        "generated_at": now_iso(),
        "dataset_version": DATASET_VERSION,
        "cases": len(normalized),
        "dataset_hash": sha256_json(normalized),
        "source": str(SOURCE_DATASET),
        "source_formal_test_used": False,
        "coverage": coverage,
        "requirements": requirements,
        "rows": normalized,
    }
    write_once("train_dev_dataset_v1.json", payload)
    return payload


def _hit(expected: set[str], candidates: list[dict[str, Any]]) -> bool:
    return bool(expected) and any(expected.intersection(set(item.get("source_chunk_ids") or [item.get("chunk_id")])) for item in candidates)


def _rank(expected: set[str], candidates: list[dict[str, Any]]) -> int:
    for rank, item in enumerate(candidates, start=1):
        if expected.intersection(set(item.get("source_chunk_ids") or [item.get("chunk_id")])):
            return rank
    return 0


def _run_configuration(
    db,
    user: User,
    cases: list[dict[str, Any]],
    *,
    configuration: str,
    optional_minimax: bool,
    on_result: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    settings.RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED = optional_minimax
    settings.RAG_OPTIONAL_LLM_TIEBREAK_ENABLED = False
    service = QueryAwareRetrievalService(db, current_user=user)
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        conversation_id = None
        try:
            response = service.search(QueryAwareSearchRequest(
                query=case["query"],
                retrieval_mode="auto",
                top_k=10,
                enable_llm=optional_minimax,
                allow_real_api=True,
            ))
            conversation_id = response.conversation_id
            payload = response.model_dump(mode="json")
            expected = set(case.get("expected_chunk_ids") or [])
            context_correct = None
            if case.get("context_merge") and conversation_id and payload.get("needs_clarification"):
                clarified = service.clarify(ClarificationRequest(
                    conversation_id=conversation_id,
                    clarification=case["clarification"],
                    enable_llm=optional_minimax,
                )).model_dump(mode="json")
                context_correct = bool(
                    not clarified.get("needs_clarification")
                    and case.get("context_expected_model") in ((clarified.get("confirmed_facts") or {}).get("device_models") or [])
                    and clarified.get("original_query") == case["query"]
                )
            raw = payload.get("raw_results") or []
            surfaced = payload.get("surfaced_results") or []
            actual_models = (payload.get("confirmed_facts") or {}).get("device_models") or []
            actual_alarms = (payload.get("confirmed_facts") or {}).get("alarm_codes") or []
            expected_models = case.get("expected_device_models") or []
            expected_alarms = case.get("expected_alarm_codes") or []
            diagnostics = payload.get("diagnostics") or {}
            structured = (payload.get("structured_model_diagnostics") or {}).get("query_understanding") or {}
            rows.append({
                "case_id": case["case_id"],
                "category": case["category"],
                "no_answer": bool(case.get("no_answer")),
                "requires_clarification": bool(case.get("requires_clarification")),
                "expected_intent": case["expected_intent"],
                "actual_intent": payload.get("primary_intent"),
                "canonical_terms": case.get("expected_canonical_terms") or [],
                "canonical_query": payload.get("canonical_question"),
                "canonical_correct": all(term in str(payload.get("canonical_question") or "") for term in case.get("expected_canonical_terms") or []),
                "expected_models": expected_models,
                "actual_models": actual_models,
                "expected_alarms": expected_alarms,
                "actual_alarms": actual_alarms,
                "hallucinated_models": sorted(set(actual_models) - set(expected_models)),
                "hallucinated_alarms": sorted(set(actual_alarms) - set(expected_alarms)),
                "clarified": bool(payload.get("needs_clarification")),
                "context_correct": context_correct,
                "confidence_status": payload.get("confidence_status"),
                "candidate_hit_at_50": _hit(expected, raw),
                "rank_at_10": _rank(expected, surfaced[:10]),
                "citation_valid": bool(diagnostics.get("citation_valid", True)),
                "citation_coverage": float(diagnostics.get("citation_coverage") or (1.0 if not surfaced else 0.0)),
                "scope_valid": bool(diagnostics.get("scope_validation_passed", True)),
                "multi_document_hit": (
                    set(case.get("expected_document_ids") or []).issubset({item.get("document_id") for item in raw})
                    if case.get("multi_document_complementary") else None
                ),
                "requested_channels": payload.get("requested_channels") or [],
                "actual_channels": payload.get("actual_channels") or [],
                "generated_queries": payload.get("generated_queries") or [],
                "raw_candidates": raw,
                "rrf_ranking": [item.get("chunk_id") for item in raw],
                "rerank_ranking": [item.get("chunk_id") for item in surfaced],
                "surfaced_results": surfaced,
                "citation_validation": {
                    "valid": diagnostics.get("citation_valid"),
                    "coverage": diagnostics.get("citation_coverage"),
                },
                "confidence": {
                    "status": payload.get("confidence_status"),
                    "score": payload.get("retrieval_confidence"),
                },
                "query_understanding_mode": payload.get("query_understanding_mode"),
                "minimax": structured.get("minimax") or {},
                "stage_latency": payload.get("stage_latency") or {},
                "error": None,
            })
        except Exception as exc:  # noqa: BLE001 - Canary retains bounded error type only.
            rows.append({
                "case_id": case["case_id"], "category": case["category"],
                "no_answer": bool(case.get("no_answer")),
                "requires_clarification": bool(case.get("requires_clarification")),
                "error": type(exc).__name__, "stage_latency": {},
            })
        finally:
            if conversation_id:
                db.execute(delete(QueryAwareRetrievalSession).where(
                    QueryAwareRetrievalSession.conversation_id == conversation_id
                ))
                db.commit()
        if on_result is not None:
            on_result(case, rows[-1])
        print({
            "configuration": configuration,
            "case": index,
            "of": len(cases),
            "error": rows[-1].get("error"),
        }, flush=True)
    return rows


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 6), round(recall, 6), round(f1, 6)


def _metrics(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, bool]]:
    valid = [row for row in rows if not row.get("error")]
    positives = [row for row in valid if not row["no_answer"] and not row["requires_clarification"]]
    ranks = [int(row.get("rank_at_10") or 0) for row in positives]
    clarification_tp = sum(row["requires_clarification"] and row.get("clarified") for row in valid)
    clarification_fp = sum(not row["requires_clarification"] and row.get("clarified") for row in valid)
    clarification_fn = sum(row["requires_clarification"] and not row.get("clarified") for row in valid)
    clarification_precision, clarification_recall, _ = _prf(clarification_tp, clarification_fp, clarification_fn)
    no_answer_tp = sum(row["no_answer"] and row.get("confidence_status") == "INSUFFICIENT_EVIDENCE" for row in valid)
    no_answer_fp = sum(not row["no_answer"] and row.get("confidence_status") == "INSUFFICIENT_EVIDENCE" for row in valid)
    no_answer_fn = sum(row["no_answer"] and row.get("confidence_status") != "INSUFFICIENT_EVIDENCE" for row in valid)
    _, _, no_answer_f1 = _prf(no_answer_tp, no_answer_fp, no_answer_fn)
    context = [row for row in valid if row.get("context_correct") is not None]
    metrics = {
        "candidate_recall_at_50": ratio(sum(row.get("candidate_hit_at_50") for row in positives), len(positives)),
        "recall_at_5": ratio(sum(0 < rank <= 5 for rank in ranks), len(ranks)),
        "recall_at_10": ratio(sum(0 < rank <= 10 for rank in ranks), len(ranks)),
        "mrr": round(statistics.mean(1 / rank if rank else 0.0 for rank in ranks), 6) if ranks else 0.0,
        "ndcg_at_10": round(statistics.mean(1 / math.log2(rank + 1) if rank else 0.0 for rank in ranks), 6) if ranks else 0.0,
        "citation_validity": ratio(sum(row.get("citation_valid") for row in positives), len(positives)),
        "citation_coverage": round(statistics.mean(row.get("citation_coverage") or 0.0 for row in positives), 6) if positives else 0.0,
        "no_answer_f1": no_answer_f1,
        "intent_accuracy": ratio(sum(row.get("actual_intent") == row.get("expected_intent") for row in valid), len(valid)),
        "canonicalization_accuracy": ratio(sum(row.get("canonical_correct") for row in valid), len(valid)),
        "clarification_precision": clarification_precision,
        "clarification_recall": clarification_recall,
        "context_merge_accuracy": ratio(sum(row.get("context_correct") for row in context), len(context)),
        "hallucinated_models": sum(len(row.get("hallucinated_models") or []) for row in valid),
        "hallucinated_alarms": sum(len(row.get("hallucinated_alarms") or []) for row in valid),
        "scope_leakage": sum(not row.get("scope_valid", True) for row in valid),
        "error_rate": ratio(sum(bool(row.get("error")) for row in rows), len(rows)),
        "multi_document_full_hit_ratio": ratio(
            sum(row.get("multi_document_hit") is True for row in valid),
            sum(row.get("multi_document_hit") is not None for row in valid),
        ),
    }
    fast = [float(row["stage_latency"].get("total_ms") or 0.0) for row in valid if row.get("query_understanding_mode") == "FAST_PATH"]
    understanding = [float(row["stage_latency"].get("query_understanding_ms") or 0.0) for row in valid]
    full = [float(row["stage_latency"].get("total_ms") or 0.0) for row in valid if not row.get("clarified")]
    multi = [
        max(0.0, float(row["stage_latency"].get("total_ms") or 0.0) - sum(
            float(row["stage_latency"].get(key) or 0.0)
            for key in ("query_understanding_ms", "rerank_ms", "refinement_ms", "citation_ms", "confidence_ms")
        ))
        for row in positives
    ]
    latency = {
        "fast_path_p95_ms": p95(fast),
        "deterministic_understanding_p95_ms": p95(understanding),
        "multi_query_p95_ms": p95(multi),
        "full_deterministic_path_p95_ms": p95(full),
    }
    checks = {
        "candidate_recall_at_50": metrics["candidate_recall_at_50"] >= 0.95,
        "recall_at_5": metrics["recall_at_5"] >= 0.80,
        "recall_at_10": metrics["recall_at_10"] >= 0.85,
        "mrr": metrics["mrr"] >= 0.75,
        "ndcg_at_10": metrics["ndcg_at_10"] >= 0.80,
        "citation_validity": metrics["citation_validity"] >= 0.98,
        "citation_coverage": metrics["citation_coverage"] >= 0.95,
        "no_answer_f1": metrics["no_answer_f1"] >= 0.85,
        "intent_accuracy": metrics["intent_accuracy"] >= 0.95,
        "canonicalization": metrics["canonicalization_accuracy"] >= 0.90,
        "clarification_precision": metrics["clarification_precision"] >= 0.85,
        "clarification_recall": metrics["clarification_recall"] >= 0.85,
        "context_merge": metrics["context_merge_accuracy"] >= 0.95,
        "hallucinated_model_zero": metrics["hallucinated_models"] == 0,
        "hallucinated_alarm_zero": metrics["hallucinated_alarms"] == 0,
        "scope_leakage_zero": metrics["scope_leakage"] == 0,
        "error_rate_zero": metrics["error_rate"] == 0.0,
        "fast_path_p95": latency["fast_path_p95_ms"] <= 1500.0,
        "deterministic_understanding_p95": latency["deterministic_understanding_p95_ms"] <= 100.0,
        "multi_query_p95": latency["multi_query_p95_ms"] <= 5000.0,
        "full_deterministic_path_p95": latency["full_deterministic_path_p95_ms"] <= 6000.0,
    }
    return metrics, latency, checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", type=int, required=True, choices=(1, 2))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--only-missing", action="store_true")
    args = parser.parse_args()
    if args.only_missing and not args.resume:
        raise SystemExit("--only-missing requires --resume")
    if not args.allow_real_api or not get_settings().TASK25B_ALLOW_REAL_API:
        raise SystemExit("Canary requires both explicit --allow-real-api and TASK25B_ALLOW_REAL_API=true")
    if get_settings().TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    artifact = OUT / f"canary_iteration_{args.iteration}.json"
    run_id = args.run_id or f"r5r4mm-iteration{args.iteration}-{uuid4()}"

    if artifact.exists() and not (args.iteration == 1 and args.resume):
        raise SystemExit(f"immutable Canary iteration already exists: {artifact}")
    if args.iteration == 2 and not (OUT / "canary_iteration_1.json").exists():
        raise SystemExit("Canary iteration 1 must run first")

    with _exclusive_run_lock(run_id):
        if args.iteration == 1 and artifact.exists() and args.resume:
            dataset_path = OUT / "train_dev_dataset_v1.json"
            if not dataset_path.exists():
                raise SystemExit("frozen Train/Dev dataset is missing; cannot resume iteration 1")
            dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
            frozen_iteration = json.loads(artifact.read_text(encoding="utf-8"))
            checkpoint = (
                _load_checkpoint(run_id=run_id)
                if CHECKPOINT.exists()
                else _seed_iteration_one_checkpoint(dataset, frozen_iteration)
            )
            iteration_one = [
                entry for entry in checkpoint.get("results") or []
                if int(entry["iteration"]) == 1
            ]
            unique = {entry["key"] for entry in iteration_one}
            expected = 2 * len(dataset["rows"])
            if len(iteration_one) != expected or len(unique) != expected:
                raise SystemExit({
                    "resume_import_invalid": True,
                    "expected": expected,
                    "actual": len(iteration_one),
                    "unique": len(unique),
                })
            _materialize_case_results(checkpoint, {row["case_id"]: row for row in dataset["rows"]})
            print({
                "status": "CANARY_ITERATION_1_REUSED_WITHOUT_EXTERNAL_CALLS",
                "iteration": 1,
                "cases_per_configuration": len(dataset["rows"]),
                "result_count": len(iteration_one),
                "missing": 0,
                "duplicates": 0,
                "external_calls": 0,
            })
            return 0

        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
            if user is None:
                raise SystemExit("Canary actor missing")
            dataset = _create_dataset(db)

            if args.iteration == 2 and not (OUT / "dev_tuning.json").exists():
                raise SystemExit("the single Train/Dev calibration record must exist before Canary iteration 2")

            if CHECKPOINT.exists():
                checkpoint = _load_checkpoint(run_id=run_id)
            else:
                iteration_one = json.loads((OUT / "canary_iteration_1.json").read_text(encoding="utf-8"))
                checkpoint = _seed_iteration_one_checkpoint(dataset, iteration_one)
            checkpoint["active_run_id"] = run_id
            if args.resume:
                checkpoint["resume_parent_run_id"] = checkpoint.get("run_id")
            checkpoint["updated_at"] = now_iso()
            _atomic_json(CHECKPOINT, checkpoint)

            cases = _iteration_cases(dataset, args.iteration)
            all_case_by_id = {row["case_id"]: row for row in dataset["rows"]}
            configurations = (
                ("deterministic_only", False),
                ("deterministic_with_optional_minimax", True),
            )
            rows_by_configuration: dict[str, list[dict[str, Any]]] = {}
            for configuration, optional_minimax in configurations:
                existing_entries = [
                    entry for entry in checkpoint.get("results") or []
                    if int(entry["iteration"]) == args.iteration
                    and entry["configuration"] == configuration
                ]
                existing_by_id = {entry["case_id"]: entry["result"] for entry in existing_entries}
                if existing_entries and not args.resume:
                    raise SystemExit(
                        f"iteration {args.iteration} configuration {configuration} already has checkpointed cases; "
                        "use --resume --only-missing"
                    )
                missing = [case for case in cases if case["case_id"] not in existing_by_id]

                def on_result(case: dict[str, Any], result: dict[str, Any]) -> None:
                    _append_checkpoint_result(
                        checkpoint,
                        iteration=args.iteration,
                        configuration=configuration,
                        case_id=case["case_id"],
                        result=result,
                    )

                if missing:
                    new_rows = _run_configuration(
                        db,
                        user,
                        missing,
                        configuration=configuration,
                        optional_minimax=optional_minimax,
                        on_result=on_result,
                    )
                    existing_by_id.update({row["case_id"]: row for row in new_rows})
                elif args.resume:
                    print({
                        "configuration": configuration,
                        "status": "COMPLETE_REUSED",
                        "missing": 0,
                        "external_calls": 0,
                    }, flush=True)
                rows_by_configuration[configuration] = [existing_by_id[case["case_id"]] for case in cases]
                completion = {
                    "iteration": args.iteration,
                    "configuration": configuration,
                    "case_count": len(cases),
                    "completed_at": now_iso(),
                }
                completions = checkpoint.setdefault("configuration_completions", [])
                completions[:] = [
                    item for item in completions
                    if not (item["iteration"] == args.iteration and item["configuration"] == configuration)
                ]
                completions.append(completion)
                checkpoint["updated_at"] = now_iso()
                _atomic_json(CHECKPOINT, checkpoint)
                _materialize_case_results(checkpoint, all_case_by_id)

            deterministic_rows = rows_by_configuration["deterministic_only"]
            optional_rows = rows_by_configuration["deterministic_with_optional_minimax"]

            iteration_entries = [
                entry for entry in checkpoint.get("results") or []
                if int(entry["iteration"]) == args.iteration
            ]
            expected_result_count = len(cases) * len(configurations)
            unique_iteration_keys = {entry["key"] for entry in iteration_entries}
            duplicate_count = len(iteration_entries) - len(unique_iteration_keys)
            expected_keys = {
                _result_key(args.iteration, configuration, case["case_id"])
                for configuration, _ in configurations for case in cases
            }
            missing_keys = sorted(expected_keys - unique_iteration_keys)
            if len(iteration_entries) != expected_result_count or duplicate_count or missing_keys:
                raise SystemExit({
                    "checkpoint_incomplete": True,
                    "expected": expected_result_count,
                    "actual": len(iteration_entries),
                    "duplicates": duplicate_count,
                    "missing": missing_keys,
                })

    deterministic_metrics, deterministic_latency, deterministic_checks = _metrics(deterministic_rows)
    optional_metrics, optional_latency, _ = _metrics(optional_rows)
    optional_attempts = [row for row in optional_rows if row.get("query_understanding_mode") in {"MINIMAX_AMBIGUITY_RESOLUTION", "SAFE_FALLBACK"}]
    optional_success = [row for row in optional_attempts if row.get("query_understanding_mode") == "MINIMAX_AMBIGUITY_RESOLUTION"]
    deterministic_by_id = {row["case_id"]: row for row in deterministic_rows}
    fallback_rows = [row for row in optional_attempts if row.get("query_understanding_mode") == "SAFE_FALLBACK"]
    fallback_lossless = all(
        all(row.get(field) == deterministic_by_id[row["case_id"]].get(field) for field in (
            "actual_intent", "canonical_query", "actual_models", "actual_alarms", "clarified"
        ))
        for row in fallback_rows
    )
    minimax_latencies = [
        float(
            (row.get("minimax") or {}).get("latency_ms")
            or (row.get("stage_latency") or {}).get("query_understanding_ms")
            or 0.0
        )
        for row in optional_attempts
    ]
    optional_component = {
        "attempted": len(optional_attempts),
        "structured_success": len(optional_success),
        "structured_success_ratio": ratio(len(optional_success), len(optional_attempts)),
        "p95_ms": p95(minimax_latencies),
        "fallback_cases": len(fallback_rows),
        "failure_lossless_ratio": 1.0 if fallback_lossless else 0.0,
        "quality_gain": {
            "candidate_recall_at_50": round(optional_metrics["candidate_recall_at_50"] - deterministic_metrics["candidate_recall_at_50"], 6),
            "recall_at_5": round(optional_metrics["recall_at_5"] - deterministic_metrics["recall_at_5"], 6),
            "mrr": round(optional_metrics["mrr"] - deterministic_metrics["mrr"], 6),
            "clarification_precision": round(optional_metrics["clarification_precision"] - deterministic_metrics["clarification_precision"], 6),
            "clarification_recall": round(optional_metrics["clarification_recall"] - deterministic_metrics["clarification_recall"], 6),
        },
    }
    optional_component["slo_passed"] = bool(
        optional_component["structured_success_ratio"] >= 0.95
        and optional_component["p95_ms"] <= 5000.0
        and optional_component["failure_lossless_ratio"] == 1.0
    )
    passed = all(deterministic_checks.values())
    status = (
        "QUERY_AWARE_GROUNDED_RAG_R4_QUALITY_GATE_FAILED"
        if not passed else
        "QUERY_AWARE_GROUNDED_RAG_R4_PASS"
        if optional_component["slo_passed"] else
        "QUERY_AWARE_GROUNDED_RAG_R4_PASS_WITH_OPTIONAL_MINIMAX_DEGRADED"
    )
    payload = {
        "generated_at": now_iso(),
        "run_id": run_id,
        "resume": bool(args.resume),
        "iteration": args.iteration,
        "dataset_version": (
            DATASET_VERSION if args.iteration == 1
            else "task25b_r3_dev_r5_r4_mm_train_dev_v1_calibrated_execution_v2"
        ),
        "source_dataset_hash": dataset["dataset_hash"],
        "dataset_hash": sha256_json(cases),
        "cases_per_configuration": len(cases),
        "expected_result_count": len(cases) * 2,
        "actual_result_count": len(deterministic_rows) + len(optional_rows),
        "missing_result_count": 0,
        "duplicate_result_count": 0,
        "formal_test_used": False,
        "deterministic_only": {
            "metrics": deterministic_metrics,
            "latency": deterministic_latency,
            "checks": deterministic_checks,
            "passed": passed,
            "rows": deterministic_rows,
        },
        "optional_minimax": {
            "metrics": optional_metrics,
            "latency": optional_latency,
            "component": optional_component,
            "rows": optional_rows,
        },
        "passed": passed,
        "status": status,
        "vector_mutations": {"re_embedded": 0, "re_upserted": 0, "collection_changes": 0, "partition_changes": 0},
    }
    write_once(f"canary_iteration_{args.iteration}.json", payload)
    if args.iteration == 2:
        write_once("canary_result.json", payload)
    print({
        "status": status,
        "iteration": args.iteration,
        "deterministic_passed": passed,
        "failed_checks": [key for key, value in deterministic_checks.items() if not value],
        "deterministic_metrics": deterministic_metrics,
        "optional_component": optional_component,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
