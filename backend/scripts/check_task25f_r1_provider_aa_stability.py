from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from task25f_common import SOURCE_DATASET, load_suite
from task25f_r1_common import RUNTIME, now_iso, read_json, safe_settings_snapshot, sha256_value, write_csv, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.vector_index_service import VectorIndexService
from app.services.vector_store_adapters.base import VectorStoreAdapterError
from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


PROGRESS = RUNTIME / "provider_aa_progress.json"
REPETITIONS = 3


def _clear_cache() -> None:
    with DashVectorAdapter._query_cache_lock:
        DashVectorAdapter._query_cache.clear()
        DashVectorAdapter._query_inflight.clear()


def _classify(error: Exception | None, candidate_count: int) -> str | None:
    if error is None:
        return "EMPTY_RESULT" if candidate_count == 0 else None
    message = str(error).casefold()
    if "429" in message:
        return "HTTP_429"
    if re.search(r"\b5\d\d\b", message):
        return "HTTP_5XX"
    if "timeout" in message or "request budget" in message:
        return "NETWORK_READ"
    if "network" in message or "connect" in message or "reset" in message:
        return "NETWORK_CONNECT"
    if "invalid json" in message or "api error code" in message:
        return "PROVIDER_INVALID_RESPONSE"
    if "collection" in message and "404" in message:
        return "INDEX_NOT_FOUND"
    if "partition" in message and "404" in message:
        return "PARTITION_NOT_FOUND"
    if "filter" in message:
        return "FILTER_ERROR"
    if "cancel" in message:
        return "CANCELLED"
    return "UNKNOWN"


def _http_status(error: Exception | None) -> int | None:
    match = re.search(r"HTTP error:\s*(\d{3})", str(error or ""), re.I)
    return int(match.group(1)) if match else None


def _provider_code(error: Exception | None) -> str | None:
    match = re.search(r"API error code:\s*([^;\s]+)", str(error or ""), re.I)
    return match.group(1)[:40] if match else None


def _anchor_type(source: dict) -> str:
    mapping = {
        "CAUSE": "CAUSE", "ACTION": "ACTION", "PROCEDURE": "PROCEDURE", "SAFETY": "SAFETY",
        "ALARM_MEANING": "ALARM", "PREREQUISITE": "PREREQUISITE", "VERIFICATION": "VERIFICATION",
        "CONFIGURATION": "COMMUNICATION", "GENERAL_INFORMATION": "SYMPTOM",
    }
    requested = source.get("expected_requested_information") or []
    return mapping.get(str(requested[0]) if requested else "", "SYMPTOM")


def _context(*, operation: str, config: dict, scope_hash: str, retry_phase: str) -> dict:
    return {
        "operation": operation,
        "query_mode": "semantic_unit" if operation == "SEMANTIC_UNIT" else "raw_vector",
        "embedding_provider": config["embedding_provider"],
        "embedding_model": config["embedding_model"],
        "embedding_dimension": config["embedding_dim"],
        "score_threshold": get_settings().VECTOR_MIN_SCORE,
        "index_version": get_settings().EMBEDDING_INDEX_VERSION,
        "retrieval_config_version": f"task25f_r1_aa_{retry_phase}",
        "scope_fingerprint": scope_hash,
    }


def _candidate_id(hit, operation: str) -> str:
    metadata = hit.metadata or {}
    if operation == "SEMANTIC_UNIT":
        return str(metadata.get("semantic_unit_id") or hit.vector_id)
    return str(metadata.get("chunk_id") or hit.vector_id)


def _run_provider_query(
    *,
    adapter: DashVectorAdapter,
    vector: list[float],
    top_k: int,
    filters: dict,
    context: dict,
    case_id: str,
    query_hash: str,
    operation: str,
    repetition: int,
    phase: str,
    client_mode: str,
) -> dict:
    _clear_cache()
    previous_client = None
    if client_mode == "independent":
        with DashVectorAdapter._client_lock:
            previous_client = DashVectorAdapter._shared_clients.pop(adapter.endpoint, None)
    started = time.perf_counter()
    error = None
    hits = []
    try:
        hits = adapter.query_vectors(
            vector=vector,
            top_k=top_k,
            filters=filters,
            request_context=context,
        )
    except Exception as exc:  # noqa: BLE001 - classified and retained without payloads.
        error = exc
    finally:
        if client_mode == "independent":
            with DashVectorAdapter._client_lock:
                fresh = DashVectorAdapter._shared_clients.pop(adapter.endpoint, None)
                if previous_client is not None and not previous_client.is_closed:
                    DashVectorAdapter._shared_clients[adapter.endpoint] = previous_client
            if fresh is not None:
                fresh.close()
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    candidate_ids = [_candidate_id(hit, operation) for hit in hits]
    scores = {candidate_id: round(float(hit.score), 8) for candidate_id, hit in zip(candidate_ids, hits)}
    failure_class = _classify(error, len(candidate_ids))
    return {
        "case_id": case_id,
        "query_hash": query_hash,
        "operation": operation,
        "phase": phase,
        "repetition": repetition,
        "request_hash": sha256_value({
            "query_hash": query_hash,
            "operation": operation,
            "vector_hash": sha256_value([round(value, 10) for value in vector]),
            "collection": adapter.collection_name,
            "partition": adapter.namespace,
            "top_k": top_k,
            "filters": filters,
            "context": context,
        }),
        "collection": adapter.collection_name,
        "partition": adapter.namespace,
        "top_k": top_k,
        "filter_hash": sha256_value(filters),
        "candidate_ids": candidate_ids,
        "candidate_count": len(candidate_ids),
        "scores": scores,
        "success": error is None,
        "failure_class": failure_class,
        "error_type": type(error).__name__ if error else None,
        "http_status": _http_status(error),
        "provider_code": _provider_code(error),
        "latency_ms": latency_ms,
        "retry_count": int(adapter.last_retries or 0),
        "client_mode": client_mode,
        "client_reused": client_mode == "shared",
        "coalesced": False,
        "concurrency_level": 1,
        "fallback_result": "DIRECT_AA_NO_FALLBACK",
        "other_channels_preserved": True,
    }


def _jaccard(left: list[str], right: list[str]) -> float:
    a, b = set(left), set(right)
    return 1.0 if not a and not b else len(a & b) / max(1, len(a | b))


def _rbo(left: list[str], right: list[str], p: float = 0.9, depth: int = 50) -> float:
    score = 0.0
    limit = min(depth, max(len(left), len(right)))
    for index in range(1, limit + 1):
        overlap = len(set(left[:index]) & set(right[:index])) / index
        score += (1 - p) * overlap * (p ** (index - 1))
    if limit:
        score += (p**limit) * len(set(left[:limit]) & set(right[:limit])) / limit
    return score


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _metrics(rows: list[dict], expected: dict[str, set[str]]) -> dict:
    pairs = []
    direct_preservation = []
    expected_recall = []
    score_drifts = []
    for (case_id, operation), group_iter in itertools.groupby(
        sorted(rows, key=lambda item: (item["case_id"], item["operation"], item["repetition"])),
        key=lambda item: (item["case_id"], item["operation"]),
    ):
        group = list(group_iter)
        successful = [item for item in group if item["success"]]
        for left, right in itertools.combinations(successful, 2):
            common = set(left["scores"]) & set(right["scores"])
            score_drifts.extend(abs(left["scores"][key] - right["scores"][key]) for key in common)
            pairs.append({
                "exact": left["candidate_ids"] == right["candidate_ids"],
                "set_exact": set(left["candidate_ids"]) == set(right["candidate_ids"]),
                "top5": left["candidate_ids"][:5] == right["candidate_ids"][:5],
                "top10": left["candidate_ids"][:10] == right["candidate_ids"][:10],
                "jaccard": _jaccard(left["candidate_ids"][:50], right["candidate_ids"][:50]),
                "rbo": _rbo(left["candidate_ids"], right["candidate_ids"]),
            })
        expected_ids = expected.get(f"{case_id}:{operation}") or set()
        if expected_ids:
            expected_recall.extend(bool(expected_ids & set(item["candidate_ids"])) for item in successful)
            if successful:
                first_direct = expected_ids & set(successful[0]["candidate_ids"])
                if first_direct:
                    direct_preservation.extend(
                        first_direct.issubset(set(item["candidate_ids"])) for item in successful[1:]
                    )
    return {
        "pair_count": len(pairs),
        "exact_candidate_order_parity": _mean([float(item["exact"]) for item in pairs]),
        "exact_candidate_set_parity": _mean([float(item["set_exact"]) for item in pairs]),
        "top5_exact_parity": _mean([float(item["top5"]) for item in pairs]),
        "top10_exact_parity": _mean([float(item["top10"]) for item in pairs]),
        "jaccard_at_50": _mean([item["jaccard"] for item in pairs]),
        "rank_biased_overlap": _mean([item["rbo"] for item in pairs]),
        "score_drift_mean": _mean(score_drifts),
        "score_drift_max": round(max(score_drifts), 8) if score_drifts else 0.0,
        "direct_evidence_preservation": (
            _mean([float(value) for value in direct_preservation]) if direct_preservation else None
        ),
        "expected_direct_evidence_recall": (
            _mean([float(value) for value in expected_recall]) if expected_recall else None
        ),
        "channel_availability": round(sum(item["success"] for item in rows) / max(1, len(rows)), 6),
        "failure_rate": round(sum(not item["success"] for item in rows) / max(1, len(rows)), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()
    if args.recompute:
        source_rows = {
            item["case_id"]: item
            for item in json.loads(SOURCE_DATASET.read_text(encoding="utf-8")).get("rows") or []
        }
        suite = load_suite()
        expected: dict[str, set[str]] = {}
        for case in suite["rows"][:30]:
            source = source_rows.get(case["source_case_id"]) or {}
            expected[f"{case['source_case_id']}:RAW_VECTOR"] = set(source.get("expected_chunk_ids") or [])
            expected[f"{case['source_case_id']}:SEMANTIC_UNIT"] = set(source.get("expected_semantic_unit_ids") or [])
        with (RUNTIME / "provider_aa_cases.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            rows = []
            for row in csv.DictReader(handle):
                rows.append({
                    **row,
                    "repetition": int(row["repetition"]),
                    "success": row["success"].casefold() == "true",
                    "candidate_ids": json.loads(row["candidate_ids"]),
                    "scores": {},
                })
        post = [item for item in rows if item["phase"] == "post_retry"]
        raw_metrics = _metrics([item for item in post if item["operation"] == "RAW_VECTOR"], expected)
        semantic_metrics = _metrics([item for item in post if item["operation"] == "SEMANTIC_UNIT"], expected)
        payload = read_json("provider_aa_stability.json", {})
        for name, metrics in (("raw_vector", raw_metrics), ("semantic_unit", semantic_metrics)):
            metrics["score_drift_mean"] = payload.get(name, {}).get("score_drift_mean", 0.0)
            metrics["score_drift_max"] = payload.get(name, {}).get("score_drift_max", 0.0)
            payload[name] = metrics
        payload["answers"]["direct_evidence_stable"] = all(
            value is None or value >= 0.99
            for value in (
                raw_metrics["direct_evidence_preservation"], semantic_metrics["direct_evidence_preservation"]
            )
        )
        payload["answers"]["top5_more_stable_than_full_set"] = (
            raw_metrics["top5_exact_parity"] > raw_metrics["exact_candidate_set_parity"]
            or semantic_metrics["top5_exact_parity"] > semantic_metrics["exact_candidate_set_parity"]
        )
        payload["metrics_recomputed_from_frozen_csv"] = True
        write_json("provider_aa_stability.json", payload)
        print(json.dumps({
            "status": payload["status"],
            "raw_direct_preservation": raw_metrics["direct_evidence_preservation"],
            "semantic_direct_preservation": semantic_metrics["direct_evidence_preservation"],
            "provider_calls": 0,
        }, ensure_ascii=False))
        return 0
    settings_snapshot = safe_settings_snapshot()
    if not (args.allow_real_api and settings_snapshot["TASK25B_ALLOW_REAL_API"]):
        raise SystemExit("explicit --allow-real-api and TASK25B_ALLOW_REAL_API=true are required")
    if settings_snapshot["TASK25B_ALLOW_FULL_REINDEX"]:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    if (RUNTIME / "provider_aa_stability.json").exists():
        raise SystemExit("provider A/A evidence already exists; refusing to overwrite")
    suite = load_suite()
    selected = list(suite["rows"][:30])
    source_rows = {
        item["case_id"]: item
        for item in json.loads(SOURCE_DATASET.read_text(encoding="utf-8")).get("rows") or []
    }
    progress = read_json(PROGRESS, {"completed_cases": [], "rows": [], "client_rows": []})
    completed = set(progress.get("completed_cases") or [])
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        scope_hash = sha256_value(scope.public_dict())
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=scope.collection_name, namespace=scope.partition_name
        )
        raw_config = service._runtime_config(provider=get_settings().EMBEDDING_PROVIDER, vector_backend="dashvector")
        embedding_service = EmbeddingService(allow_real_api=True)
        for index, case in enumerate(selected, start=1):
            case_id = case["source_case_id"]
            if case_id in completed:
                continue
            embedded = embedding_service.embed_query(case["query"], provider=raw_config["embedding_provider"])
            vector = embedded.vectors[0]
            source = source_rows.get(case_id) or {}
            anchor_type = _anchor_type(source)
            raw_adapter = service._adapter(raw_config)
            semantic_service = VectorIndexService(
                db, allow_real_api=True, collection_name=scope.collection_name, namespace="pilot_r5_query_aware"
            )
            semantic_config = semantic_service._runtime_config(
                provider=get_settings().EMBEDDING_PROVIDER, vector_backend="dashvector"
            )
            semantic_adapter = semantic_service._adapter(semantic_config)
            raw_filters = {"review_status": "approved", "parse_status": "parsed", "status": "active"}
            semantic_filters = {"object_type": "maintenance_semantic_unit", "anchor_type": anchor_type}
            pre_retry_adapter = DashVectorAdapter(
                endpoint=semantic_adapter.endpoint,
                api_key=semantic_adapter.api_key,
                collection_name=semantic_adapter.collection_name,
                namespace=semantic_adapter.namespace,
                dimension=semantic_adapter.dimension,
                metric=semantic_adapter.metric,
                dtype=semantic_adapter.dtype,
                timeout_seconds=semantic_adapter.timeout_seconds,
                allow_real_api=True,
                embedding_provider=semantic_config["embedding_provider"],
                embedding_model=semantic_config["embedding_model"],
                index_version=get_settings().EMBEDDING_INDEX_VERSION,
                retrieval_config_version="task25f_r1_aa_pre_retry",
                max_query_retries=0,
            )
            for repetition in range(1, REPETITIONS + 1):
                progress["rows"].append(_run_provider_query(
                    adapter=pre_retry_adapter, vector=vector, top_k=40, filters=semantic_filters,
                    context=_context(
                        operation="SEMANTIC_UNIT", config=semantic_config, scope_hash=scope_hash,
                        retry_phase="pre_retry",
                    ),
                    case_id=case_id, query_hash=case["query_hash"], operation="SEMANTIC_UNIT",
                    repetition=repetition, phase="pre_retry", client_mode="shared",
                ))
                progress["rows"].append(_run_provider_query(
                    adapter=raw_adapter, vector=vector, top_k=50, filters=raw_filters,
                    context=_context(
                        operation="RAW_VECTOR", config=raw_config, scope_hash=scope_hash,
                        retry_phase="post_retry",
                    ),
                    case_id=case_id, query_hash=case["query_hash"], operation="RAW_VECTOR",
                    repetition=repetition, phase="post_retry", client_mode="shared",
                ))
                progress["rows"].append(_run_provider_query(
                    adapter=semantic_adapter, vector=vector, top_k=40, filters=semantic_filters,
                    context=_context(
                        operation="SEMANTIC_UNIT", config=semantic_config, scope_hash=scope_hash,
                        retry_phase="post_retry",
                    ),
                    case_id=case_id, query_hash=case["query_hash"], operation="SEMANTIC_UNIT",
                    repetition=repetition, phase="post_retry", client_mode="shared",
                ))
            if index <= 5:
                for operation, adapter, config, filters, top_k in (
                    ("RAW_VECTOR", raw_adapter, raw_config, raw_filters, 50),
                    ("SEMANTIC_UNIT", semantic_adapter, semantic_config, semantic_filters, 40),
                ):
                    progress["client_rows"].append(_run_provider_query(
                        adapter=adapter, vector=vector, top_k=top_k, filters=filters,
                        context=_context(
                            operation=operation, config=config, scope_hash=scope_hash,
                            retry_phase="client_comparison",
                        ),
                        case_id=case_id, query_hash=case["query_hash"], operation=operation,
                        repetition=1, phase="client_comparison", client_mode="independent",
                    ))
            progress["completed_cases"].append(case_id)
            progress["updated_at"] = now_iso()
            write_json(PROGRESS, progress)
            print(json.dumps({
                "progress": f"{index}/30", "case_id": case_id,
                "post_failures": sum(
                    not row["success"] for row in progress["rows"]
                    if row["phase"] == "post_retry" and row["case_id"] == case_id
                ),
            }, ensure_ascii=False), flush=True)
    post_rows = [item for item in progress["rows"] if item["phase"] == "post_retry"]
    pre_rows = [item for item in progress["rows"] if item["phase"] == "pre_retry"]
    expected: dict[str, set[str]] = {}
    for case in selected:
        source = source_rows.get(case["source_case_id"]) or {}
        expected[f"{case['source_case_id']}:RAW_VECTOR"] = set(source.get("expected_chunk_ids") or [])
        expected[f"{case['source_case_id']}:SEMANTIC_UNIT"] = set(source.get("expected_semantic_unit_ids") or [])
    raw_rows = [item for item in post_rows if item["operation"] == "RAW_VECTOR"]
    semantic_rows = [item for item in post_rows if item["operation"] == "SEMANTIC_UNIT"]
    raw_metrics = _metrics(raw_rows, expected)
    semantic_metrics = _metrics(semantic_rows, expected)
    pre_metrics = _metrics(pre_rows, expected)
    client_matches = []
    for independent in progress.get("client_rows") or []:
        shared = next((
            item for item in post_rows
            if item["case_id"] == independent["case_id"]
            and item["operation"] == independent["operation"]
            and item["repetition"] == 1
        ), None)
        if shared and shared["success"] and independent["success"]:
            client_matches.append(shared["candidate_ids"] == independent["candidate_ids"])
    failures = [item for item in post_rows if not item["success"]]
    failure_classes = Counter(item["failure_class"] or "UNKNOWN" for item in failures)
    payload = {
        "status": "PASSED" if not failures else "FAILED",
        "case_count": 30,
        "repetitions": REPETITIONS,
        "same_request_enforced": True,
        "same_vector_per_case": True,
        "coalescing_disabled_for_aa": True,
        "raw_vector": raw_metrics,
        "semantic_unit": semantic_metrics,
        "pre_retry_semantic": pre_metrics,
        "post_retry_failure_count": len(failures),
        "post_retry_failure_rate": round(len(failures) / max(1, len(post_rows)), 6),
        "pre_retry_failure_count": sum(not item["success"] for item in pre_rows),
        "retry_success_count": max(
            0, sum(not item["success"] for item in pre_rows) - sum(not item["success"] for item in semantic_rows)
        ),
        "failure_classes": dict(sorted(failure_classes.items())),
        "shared_vs_independent_client": {
            "comparisons": len(client_matches),
            "exact_candidate_order_parity": round(sum(client_matches) / len(client_matches), 6) if client_matches else None,
        },
        "answers": {
            "same_real_request_naturally_varies": raw_metrics["exact_candidate_order_parity"] < 1.0 or semantic_metrics["exact_candidate_order_parity"] < 1.0,
            "top5_more_stable_than_full_set": (
                raw_metrics["top5_exact_parity"] > raw_metrics["exact_candidate_set_parity"]
                or semantic_metrics["top5_exact_parity"] > semantic_metrics["exact_candidate_set_parity"]
            ),
            "direct_evidence_stable": all(
                value is None or value >= 0.99
                for value in (
                    raw_metrics["direct_evidence_preservation"], semantic_metrics["direct_evidence_preservation"]
                )
            ),
            "sequential_failures_remain": bool(failures),
            "shared_independent_difference": bool(client_matches) and not all(client_matches),
        },
        "rows_recorded": len(progress["rows"]),
        "client_comparison_rows": len(progress.get("client_rows") or []),
        "contains_vectors": False,
        "contains_query_text": False,
    }
    write_json("provider_aa_stability.json", payload, overwrite=False)
    csv_rows = [*progress["rows"], *(progress.get("client_rows") or [])]
    write_csv(
        "provider_aa_cases.csv",
        [{
            **{key: row.get(key) for key in (
                "case_id", "query_hash", "operation", "phase", "repetition", "request_hash",
                "collection", "partition", "top_k", "filter_hash", "candidate_count", "success",
                "failure_class", "error_type", "http_status", "provider_code", "latency_ms",
                "retry_count", "client_mode", "client_reused", "coalesced", "concurrency_level",
                "fallback_result", "other_channels_preserved",
            )},
            "candidate_ids": json.dumps(row["candidate_ids"], ensure_ascii=False),
        } for row in csv_rows],
        [
            "case_id", "query_hash", "operation", "phase", "repetition", "request_hash",
            "collection", "partition", "top_k", "filter_hash", "candidate_ids", "candidate_count",
            "success", "failure_class", "error_type", "http_status", "provider_code", "latency_ms",
            "retry_count", "client_mode", "client_reused", "coalesced", "concurrency_level",
            "fallback_result", "other_channels_preserved",
        ],
    )
    if PROGRESS.exists():
        PROGRESS.unlink()
    print(json.dumps({
        "status": payload["status"], "cases": 30, "repetitions": REPETITIONS,
        "raw_exact": raw_metrics["exact_candidate_set_parity"],
        "semantic_exact": semantic_metrics["exact_candidate_set_parity"],
        "post_failures": len(failures), "pre_failures": payload["pre_retry_failure_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
