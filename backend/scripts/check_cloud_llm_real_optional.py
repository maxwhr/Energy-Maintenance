from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.services.external_api_provider_registry import ExternalApiProviderRegistry  # noqa: E402
from scripts.task24c_real_api_common import (  # noqa: E402
    MARKER,
    api_data,
    contains_sensitive_value,
    login,
    missing_config,
    print_result,
    provider_config_summary,
    query_string,
    request_json,
    write_result,
)


def _seed_providers() -> None:
    with SessionLocal() as db:
        ExternalApiProviderRegistry(db).seed_defaults()
        db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional real Cloud LLM acceptance check.")
    parser.add_argument("--allow-real-api", action="store_true", help="Actually call the configured cloud LLM provider.")
    parser.add_argument("--base-url", default=None, help="API base URL, defaults to TASK24C_API_BASE_URL or 127.0.0.1:8010/api.")
    args = parser.parse_args()

    if not args.allow_real_api:
        result = {
            "provider": "cloud_llm",
            "status": "skipped",
            "reason": "real cloud LLM check requires --allow-real-api",
            "real_external_api_used": False,
            "config": provider_config_summary()["cloud_llm"],
        }
        write_result("cloud_llm_real_result.json", result)
        print_result(result)
        return 0

    missing = missing_config("cloud_llm")
    if missing:
        result = {
            "provider": "cloud_llm",
            "status": "blocked",
            "missing_or_invalid": missing,
            "real_external_api_used": False,
            "config": provider_config_summary()["cloud_llm"],
        }
        write_result("cloud_llm_real_result.json", result)
        print_result(result)
        return 0

    _seed_providers()
    token, user = login(args.base_url)
    prompt = (
        f"{MARKER}: Provide a concise safety-aware maintenance note for a Huawei SUN2000 PV inverter alarm. "
        "Mention that field engineer confirmation is required."
    )
    status, response = request_json(
        "POST",
        "/model-gateway/chat",
        base_url=args.base_url,
        token=token,
        payload={
            "provider": "cloud_openai",
            "task_type": "qa",
            "allow_fallback": False,
            "prompt": prompt,
        },
        timeout=90,
    )
    chat = api_data("cloud model gateway chat", status, response)
    chat_success = bool(isinstance(chat, dict) and chat.get("success") and chat.get("content") and chat.get("provider") == "cloud_openai")
    trace_id = chat.get("trace_id") if isinstance(chat, dict) else None

    status, response = request_json(
        "POST",
        "/external-apis/check-real",
        base_url=args.base_url,
        token=token,
        payload={
            "provider_code": "cloud_openai",
            "capability": "text_chat",
            "input_summary": {
                "prompt": prompt,
                "acceptance_marker": MARKER,
                "expected_output": "short PV inverter maintenance answer",
            },
            "real_run": True,
        },
        timeout=90,
    )
    external = api_data("external API cloud check-real", status, response)
    external_success = bool(isinstance(external, dict) and external.get("success") and external.get("external_api_called"))

    query = query_string({"provider": "cloud_openai", "page": 1, "page_size": 5})
    status, response = request_json("GET", f"/model-gateway/logs?{query}", base_url=args.base_url, token=token)
    logs = api_data("model gateway logs", status, response)
    log_items = logs.get("items") if isinstance(logs, dict) else []
    log_found = any(item.get("trace_id") == trace_id for item in log_items if isinstance(item, dict))

    sensitive = contains_sensitive_value(chat) or contains_sensitive_value(external) or contains_sensitive_value(logs)
    status_value = "passed" if chat_success and external_success and log_found and not sensitive else "failed"
    result = {
        "provider": "cloud_llm",
        "status": status_value,
        "real_external_api_used": bool(chat_success or external_success),
        "model_gateway": {
            "success": chat_success,
            "trace_id": trace_id,
            "provider": chat.get("provider") if isinstance(chat, dict) else None,
            "requested_provider": chat.get("requested_provider") if isinstance(chat, dict) else None,
            "fallback_used": chat.get("fallback_used") if isinstance(chat, dict) else None,
            "latency_ms": chat.get("latency_ms") if isinstance(chat, dict) else None,
            "content_length": len(str(chat.get("content") or "")) if isinstance(chat, dict) else 0,
        },
        "external_api_gateway": {
            "success": external_success,
            "trace_id": external.get("trace_id") if isinstance(external, dict) else None,
            "status": external.get("status") if isinstance(external, dict) else None,
            "latency_ms": external.get("latency_ms") if isinstance(external, dict) else None,
        },
        "logs": {"model_log_found": log_found, "sanitized": not sensitive},
        "fallback": "Model Gateway rule_based fallback remains enabled for normal calls when allow_fallback=true.",
        "config": provider_config_summary()["cloud_llm"],
        "current_user": {"username": user.get("username"), "role": user.get("role")},
    }
    write_result("cloud_llm_real_result.json", result)
    print_result(result)
    return 0 if status_value == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
