from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

from task25f_common import load_suite, run_case
from task25f_r1_common import (
    RUNTIME,
    TASK25F_RUNTIME,
    now_iso,
    read_json,
    safe_settings_snapshot,
    sha256_file,
    sha256_text,
    sha256_value,
    write_json,
    write_jsonl,
)

from app.services.multi_query_retrieval_service import MultiQueryRetrievalService
from app.services.rag_raw_channel_snapshot import (
    RawRetrievalCandidateSnapshot,
    RawRetrievalChannelSnapshot,
)
from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


PROGRESS = RUNTIME / "channel_snapshot_progress.json"


def _safe_understanding(value) -> dict:
    names = (
        "primary_intent",
        "requested_information",
        "device_models",
        "alarm_codes",
        "alarm_names",
        "components",
        "symptoms",
        "confirmed_facts",
        "missing_information",
        "ambiguity",
        "needs_clarification",
        "completeness_status",
        "query_understanding_mode",
    )
    return {name: getattr(value, name, None) for name in names}


def _safe_plan(plan) -> dict:
    return {
        "requested_channels": list(plan.requested_channels),
        "candidate_top_k": int(plan.candidate_top_k),
        "fusion_candidate_limit": int(plan.fusion_candidate_limit),
        "per_channel_identity_limit": int(plan.per_channel_identity_limit),
        "channel_candidate_budgets": dict(plan.channel_candidate_budgets),
        "channel_weights": dict(plan.channel_weights),
        "query_weights": dict(plan.query_weights),
        "anchor_types": list(plan.anchor_types),
        "query_variants": [
            {
                "variant_id": f"v{index}",
                "variant_type": item.variant_type,
                "variant_hash": sha256_text(item.query),
            }
            for index, item in enumerate(plan.query_variants, start=1)
        ],
    }


def _candidate(item, rank: int) -> RawRetrievalCandidateSnapshot:
    locator = item.source_locator or {}
    section = locator.get("heading_path") or locator.get("section") or item.section_title
    source_ids = tuple(str(value) for value in (item.source_chunk_ids or [item.chunk_id]))
    scores = [float(value) for value in item.raw_scores.values() if isinstance(value, (int, float))]
    score = round(max(scores, default=0.0), 8)
    metadata_hash = sha256_value({
        "candidate_id": item.candidate_id,
        "document_id": item.document_id,
        "chunk_id": item.chunk_id,
        "semantic_unit_id": item.semantic_unit_id,
        "section": section,
        "source_chunk_ids": source_ids,
    })
    return RawRetrievalCandidateSnapshot(
        provider_candidate_id=str(item.semantic_unit_id or item.candidate_id),
        evidence_source_type="SEMANTIC_UNIT" if item.semantic_unit_id else "CHUNK",
        score=score,
        rank=rank,
        metadata_hash=metadata_hash,
        document_id=str(item.document_id),
        chunk_id=str(item.chunk_id),
        semantic_unit_id=str(item.semantic_unit_id) if item.semantic_unit_id else None,
        section_id=str(section) if section else None,
        source_chunk_ids=source_ids,
    )


def _capture_case(case: dict, config_fingerprint: str) -> tuple[list[dict], dict]:
    records: list[dict] = []
    context: dict = {}
    lock = threading.Lock()
    original_timed_fetch = MultiQueryRetrievalService._timed_fetch
    original_retrieve = MultiQueryRetrievalService.retrieve

    def retrieve_wrapper(instance, *args, **kwargs):
        plan = kwargs["plan"]
        understanding = kwargs["understanding"]
        scope = kwargs["scope"]
        with lock:
            context.update({
                "understanding": _safe_understanding(understanding),
                "understanding_hash": sha256_value(_safe_understanding(understanding)),
                "plan": _safe_plan(plan),
                "scope": scope.public_dict(),
                "scope_fingerprint": sha256_value(scope.public_dict()),
            })
        return original_retrieve(instance, *args, **kwargs)

    def timed_fetch_wrapper(instance, job, **kwargs):
        channel, query, variant_type = job
        scope = kwargs["scope"]
        vector = kwargs.get("query_vector")
        vector_hash = sha256_value([round(float(value), 10) for value in vector]) if vector else None
        variant_hash = sha256_text(query)
        variants = (context.get("plan") or {}).get("query_variants") or []
        variant_id = next(
            (item["variant_id"] for item in variants if item["variant_hash"] == variant_hash),
            f"vh:{variant_hash[:12]}",
        )
        filters = {
            "scope_fingerprint": context.get("scope_fingerprint") or sha256_value(scope.public_dict()),
            "object_type": "maintenance_semantic_unit" if channel == "SEMANTIC_UNIT" else None,
            "anchor_types": kwargs.get("anchor_types") or [],
        }
        request_identity = {
            "provider": "postgresql" if channel in {"EXACT_KEYWORD", "SCOPED_KEYWORD", "KG_ALIAS"} else "dashvector",
            "operation": channel,
            "collection": scope.collection_name,
            "partition": "pilot_r5_query_aware" if channel == "SEMANTIC_UNIT" else scope.partition_name,
            "top_k": int(kwargs["top_k"]),
            "filter_hash": sha256_value(filters),
            "vector_hash": vector_hash,
            "variant_hash": variant_hash,
            "retrieval_config_version": config_fingerprint,
        }
        try:
            values, elapsed_ms, trace = original_timed_fetch(instance, job, **kwargs)
            status = "SUCCESS" if values else "EMPTY_RESULT"
            error_type = None
            return values, elapsed_ms, trace
        except Exception as exc:
            values = []
            elapsed_ms = 0.0
            trace = {}
            status = "FAILED"
            error_type = type(exc).__name__
            raise
        finally:
            candidates = tuple(_candidate(item, rank) for rank, item in enumerate(values, start=1))
            snapshot = RawRetrievalChannelSnapshot.create(
                case_id=str(case["source_case_id"]),
                query_hash=str(case["query_hash"]),
                scope_fingerprint=str(context.get("scope_fingerprint") or sha256_value(scope.public_dict())),
                planner_version="RetrievalPlanService/current-frozen-task25f-r1",
                retrieval_config_version=config_fingerprint,
                channel=channel,
                variant_id=variant_id,
                variant_type=variant_type,
                variant_hash=variant_hash,
                collection=scope.collection_name,
                partition=request_identity["partition"],
                top_k=int(kwargs["top_k"]),
                filter_hash=request_identity["filter_hash"],
                vector_hash=vector_hash,
                response_status=status,
                provider_request_hash=sha256_value(request_identity),
                candidates=candidates,
                error_type=error_type,
            )
            row = snapshot.public_dict()
            row["latency_ms"] = round(float(elapsed_ms), 3)
            row["trace_hash"] = sha256_value(trace or {})
            with lock:
                records.append(row)

    with DashVectorAdapter._query_cache_lock:
        DashVectorAdapter._query_cache.clear()
        DashVectorAdapter._query_inflight.clear()
    with patch.object(MultiQueryRetrievalService, "retrieve", retrieve_wrapper), patch.object(
        MultiQueryRetrievalService, "_timed_fetch", timed_fetch_wrapper
    ):
        result = run_case(case, allow_real_api=True, cache_mode="off")
    context["reference_output"] = {
        "query_understanding_hash": context.get("understanding_hash"),
        "query_variant_hashes": [item["variant_hash"] for item in (context.get("plan") or {}).get("query_variants") or []],
        "requested_channels": result["result"].get("requested_channels") or [],
        "actual_channels": result["result"].get("actual_channels") or [],
        "candidate_identities": result["result"].get("candidate_identities") or [],
        "top5_identities": result["result"].get("top5_identities") or [],
        "top10_identities": result["result"].get("top10_identities") or [],
        "citation_identities": result["result"].get("citation_identities") or [],
        "citation_locators": result["result"].get("citation_locators") or [],
        "confidence_status": result["result"].get("confidence_status"),
        "no_answer": result["result"].get("no_answer"),
        "needs_clarification": result["result"].get("needs_clarification"),
        "scope_leakage": result["result"].get("scope_leakage"),
    }
    context.update({
        "case_id": case["source_case_id"],
        "query_hash": case["query_hash"],
        "tags": case.get("tags") or [],
        "provider_request_count": result["provider"]["request_count"],
        "captured_at": now_iso(),
    })
    channel_priority = {name: index for index, name in enumerate(
        ("EXACT_KEYWORD", "SCOPED_KEYWORD", "RAW_VECTOR", "SEMANTIC_UNIT", "KG_ALIAS")
    )}
    records.sort(key=lambda row: (
        channel_priority.get(row["channel"], 99), row["variant_id"],
        row["provider_request_hash"],
    ))
    return records, context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = safe_settings_snapshot()
    if not (args.allow_real_api and settings["TASK25B_ALLOW_REAL_API"]):
        raise SystemExit("explicit --allow-real-api and TASK25B_ALLOW_REAL_API=true are required")
    if settings["TASK25B_ALLOW_FULL_REINDEX"]:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    if (RUNTIME / "channel_snapshots.jsonl").exists() or (RUNTIME / "channel_snapshot_manifest.json").exists():
        raise SystemExit("immutable Task 25F-R1 channel snapshots already exist; refusing to overwrite")
    frozen = read_json("task25f_snapshot.json", {})
    if not frozen:
        raise SystemExit("freeze_task25f_r1_snapshot.py must run first")
    config_fingerprint = str(frozen["config_fingerprint"])
    suite = load_suite()
    progress = read_json(PROGRESS, {"cases": [], "records": []})
    completed = {item["case_id"] for item in progress.get("cases") or []}
    for index, case in enumerate(suite["rows"], start=1):
        if case["source_case_id"] in completed:
            continue
        try:
            records, context = _capture_case(case, config_fingerprint)
        except Exception as exc:
            print(json.dumps({
                "progress": f"{index}/{suite['case_count']}",
                "case_id": case["source_case_id"],
                "error": type(exc).__name__,
            }, ensure_ascii=False), flush=True)
            raise
        progress["cases"].append(context)
        progress["records"].extend(records)
        progress["updated_at"] = now_iso()
        write_json(PROGRESS, progress)
        print(json.dumps({
            "progress": f"{index}/{suite['case_count']}",
            "case_id": case["source_case_id"],
            "channel_records": len(records),
            "provider_requests": context["provider_request_count"],
        }, ensure_ascii=False), flush=True)
    case_order = {row["source_case_id"]: row["ordinal"] for row in suite["rows"]}
    contexts = sorted(progress["cases"], key=lambda row: case_order[row["case_id"]])
    records = sorted(progress["records"], key=lambda row: (
        case_order[row["case_id"]], row["channel"], row["variant_id"], row["provider_request_hash"]
    ))
    write_jsonl("channel_snapshots.jsonl", records, overwrite=False)
    snapshot_path = RUNTIME / "channel_snapshots.jsonl"
    manifest_body = {
        "version": "task25f_r1_channel_snapshot_manifest_v1",
        "created_at": now_iso(),
        "immutable": True,
        "source_task25f_manifest_hash": frozen["task25f_hash_manifest"],
        "query_suite_sha256": suite["dataset_sha256"],
        "case_count": len(contexts),
        "channel_record_count": len(records),
        "candidate_record_count": sum(len(item.get("candidates") or []) for item in records),
        "channels": sorted({item["channel"] for item in records}),
        "provider_failures": sum(item["response_status"] == "FAILED" for item in records),
        "contains_vectors": False,
        "contains_query_text": False,
        "contains_candidate_content": False,
        "contexts": contexts,
        "snapshot_file": "channel_snapshots.jsonl",
        "snapshot_file_sha256": sha256_file(snapshot_path),
    }
    manifest_body["manifest_hash"] = sha256_value(manifest_body)
    write_json("channel_snapshot_manifest.json", manifest_body, overwrite=False)
    if PROGRESS.exists():
        PROGRESS.unlink()
    print(json.dumps({
        "status": "TASK25F_R1_CHANNEL_SNAPSHOT_FROZEN",
        "cases": len(contexts),
        "records": len(records),
        "candidates": manifest_body["candidate_record_count"],
        "provider_failures": manifest_body["provider_failures"],
        "manifest_hash": manifest_body["manifest_hash"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
