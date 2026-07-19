from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from task25b_r3_dev_r5_r6_common import ROOT, now_iso, write_json


EXPECTED_PROVIDER_STATUS = "QWEN3_RERANK_CONFIG_MISSING"


def _unwrap(payload: dict[str, Any]) -> Any:
    return payload.get("data") if "data" in payload else payload


def _credentials() -> dict[str, Any]:
    path = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    if not path.exists():
        raise SystemExit("private test credentials are not prepared")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8012")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    settings = get_settings()
    credentials = _credentials()["admin"]
    checks: dict[str, bool] = {}
    safe_evidence: dict[str, Any] = {}

    with httpx.Client(base_url=base_url, timeout=httpx.Timeout(60.0), trust_env=False) as client:
        health_response = client.get("/api/health")
        health = _unwrap(health_response.json())
        checks["health_ok"] = health_response.status_code == 200 and health.get("status") == "running"

        login_response = client.post(
            "/api/auth/login",
            json={"username": credentials["username"], "password": credentials["password"]},
        )
        login = _unwrap(login_response.json())
        token = login.get("access_token") or ""
        checks["admin_login"] = login_response.status_code == 200 and login.get("user", {}).get("role") == "admin"
        headers = {"Authorization": f"Bearer {token}"}

        summary_response = client.get("/api/system/retrieval-quality/r5/summary", headers=headers)
        summary = _unwrap(summary_response.json())
        r6_summary = summary.get("r5_r6") or {}
        checks["quality_summary_ok"] = summary_response.status_code == 200
        vector_integrity = r6_summary.get("vector_integrity") or {}
        checks["summary_config_status"] = r6_summary.get("final_status") == EXPECTED_PROVIDER_STATUS
        checks["summary_read_only"] = (
            vector_integrity.get("re_embedded") == 0
            and vector_integrity.get("re_upserted") == 0
            and vector_integrity.get("default_partition_affected") is False
        )

        query_response = client.post(
            "/api/retrieval/query-aware-search",
            headers=headers,
            json={
                "query": "通信频繁中断，原因是什么，应该如何处理并验证恢复？",
                "retrieval_mode": "auto",
                "top_k": 5,
                "enable_llm": True,
                "allow_real_api": False,
            },
        )
        query = _unwrap(query_response.json())
        dedicated = query.get("dedicated_rerank") or {}
        diagnostics = query.get("diagnostics") or {}
        structured_dedicated = (query.get("structured_model_diagnostics") or {}).get("dedicated_rerank") or {}
        minimax = query.get("minimax_tiebreak") or {}
        checks["query_ok"] = query_response.status_code == 200
        checks["dedicated_contract_present"] = (
            dedicated.get("model") == "qwen3-rerank"
            and dedicated.get("instruct_version") == "task25b_r3_dev_r5_r6_instruct_v1"
        )
        checks["config_missing_is_explicit"] = (
            dedicated.get("provider_status") == EXPECTED_PROVIDER_STATUS
            and dedicated.get("fallback_reason") == EXPECTED_PROVIDER_STATUS
            and dedicated.get("fallback") is True
        )
        checks["deterministic_fallback_preserved"] = (
            structured_dedicated.get("fallback_order_preserved") is True
            and query.get("post_rerank_constraints", {}).get("status")
            == "SKIPPED_TO_PRESERVE_DETERMINISTIC_FALLBACK_ORDER"
        )
        checks["minimax_not_in_ranking"] = minimax.get("called") is False
        checks["candidate_boundary_preserved"] = (
            diagnostics.get("candidate_additions_by_rerank") == 0
            and diagnostics.get("candidate_source_modifications_by_rerank") == 0
        )
        checks["citation_contract_valid"] = (
            len(query.get("invalid_citations") or []) == 0
            and 0.0 <= float(query.get("citation_validity_ratio") or 0.0) <= 1.0
            and 0.0 <= float(query.get("citation_coverage_ratio") or 0.0) <= 1.0
        )
        rerank_document_descriptors = structured_dedicated.get("rerank_documents") or []
        safe_descriptor_keys = {"candidate_id", "text_hash", "text_length"}
        descriptors_are_metadata_only = all(
            isinstance(item, dict) and set(item).issubset(safe_descriptor_keys)
            for item in rerank_document_descriptors
        )
        public_json = json.dumps(query, ensure_ascii=False).lower()
        checks["no_secret_or_full_rerank_text"] = (
            "dashscope_api_key" not in public_json
            and "authorization: bearer" not in public_json
            and credentials["password"].lower() not in public_json
            and descriptors_are_metadata_only
        )

        safe_evidence = {
            "health_status": health.get("status"),
            "quality_summary_http_status": summary_response.status_code,
            "query_http_status": query_response.status_code,
            "provider_status": dedicated.get("provider_status"),
            "fallback_reason": dedicated.get("fallback_reason"),
            "fallback_order_preserved": structured_dedicated.get("fallback_order_preserved"),
            "post_guard_status": query.get("post_rerank_constraints", {}).get("status"),
            "minimax_called_for_ranking": minimax.get("called"),
            "surfaced_results": len(query.get("surfaced_results") or []),
            "valid_citations": len(query.get("valid_citations") or []),
            "invalid_citations": len(query.get("invalid_citations") or []),
        }

    checks["full_reindex_disabled"] = not settings.TASK25B_ALLOW_FULL_REINDEX
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "generated_at": now_iso(),
        "task": "Task 25B-R3-DEV-R5-R6 final smoke",
        "status": "PASSED" if not failures else "FAILED",
        "base_url": base_url,
        "real_qwen_api_called": False,
        "real_embedding_api_called": False,
        "dashvector_mutation_called": False,
        "credentials_output": False,
        "checks": checks,
        "failures": failures,
        "evidence": safe_evidence,
    }
    write_json("final_smoke.json", payload)
    print(json.dumps({"status": payload["status"], "checks": len(checks), "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
