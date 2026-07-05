from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.services.external_api_provider_registry import ExternalApiProviderRegistry  # noqa: E402
from scripts.seed_agent_runtime import main as seed_agent_runtime  # noqa: E402
from scripts.task24c_real_api_common import (  # noqa: E402
    MARKER,
    api_data,
    login,
    missing_config,
    print_result,
    request_json,
    write_result,
)


def _seed() -> None:
    if seed_agent_runtime() != 0:
        raise RuntimeError("seed_agent_runtime.py failed")
    with SessionLocal() as db:
        ExternalApiProviderRegistry(db).seed_defaults()
        db.commit()


def _extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"status": "failed", "error": "child script did not return JSON"}
    try:
        parsed = json.loads(stdout[start : end + 1])
    except json.JSONDecodeError as exc:
        return {"status": "failed", "error": f"child script returned invalid JSON: {exc}"}
    return parsed if isinstance(parsed, dict) else {"status": "failed", "error": "child JSON is not an object"}


def _run_child(script_name: str, *, base_url: str | None) -> dict[str, Any]:
    command = [sys.executable, str(SCRIPT_DIR / script_name), "--allow-real-api"]
    if base_url:
        command.extend(["--base-url", base_url])
    completed = subprocess.run(command, cwd=str(BACKEND_DIR), text=True, capture_output=True, timeout=300)
    result = _extract_json(completed.stdout)
    if completed.returncode != 0 and result.get("status") != "blocked":
        result["status"] = "failed"
        result["returncode"] = completed.returncode
        result["stderr_sanitized_note"] = "Child script stderr was suppressed to avoid leaking local paths or secrets."
    return result


def _create_agent_run(
    *,
    token: str,
    base_url: str | None,
    agent_code: str,
    tools: list[str],
    media_id: str | None = None,
    tool_inputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "agent_code": agent_code,
        "input_text": f"{MARKER} verify agent provider integration without creating formal business objects.",
        "media_ids": [media_id] if media_id else [],
        "tools": tools,
        "context": {
            "agent_code": agent_code,
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "source": "task24c_real_agent_provider_integration",
        },
        "tool_inputs": tool_inputs or {},
        "dry_run": False,
        "mock_run": False,
        "requires_approval": False,
    }
    status, response = request_json("POST", "/agents/runs", base_url=base_url, token=token, payload=payload, timeout=120)
    run = api_data("agent run", status, response)
    run_id = run.get("run_id") if isinstance(run, dict) else None
    if not run_id:
        raise RuntimeError("agent run did not return run_id")
    status, response = request_json("GET", f"/agents/runs/{run_id}", base_url=base_url, token=token, timeout=60)
    return api_data("agent run detail", status, response)


def _tool_call(detail: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    for item in detail.get("tool_calls") or []:
        if item.get("tool_name") == tool_name:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 24C agent/provider integration check.")
    parser.add_argument("--allow-real-api", action="store_true", help="Allow provider child scripts to make real calls when configured.")
    parser.add_argument("--base-url", default=None, help="API base URL, defaults to TASK24C_API_BASE_URL or 127.0.0.1:8010/api.")
    args = parser.parse_args()

    if not args.allow_real_api:
        result = {
            "status": "skipped",
            "reason": "agent real provider integration requires --allow-real-api",
            "real_external_api_used": False,
        }
        write_result("real_agent_provider_integration_result.json", result)
        print_result(result)
        return 0

    _seed()
    token, user = login(args.base_url)
    child_results: dict[str, dict[str, Any]] = {}
    agent_results: dict[str, dict[str, Any]] = {}

    if not missing_config("mimo"):
        child_results["mimo"] = _run_child("check_mimo_real_optional.py", base_url=args.base_url)
        media_id = child_results["mimo"].get("media_id")
        if child_results["mimo"].get("status") == "passed" and media_id:
            detail = _create_agent_run(
                token=token,
                base_url=args.base_url,
                agent_code="retrieval_qa_agent",
                media_id=media_id,
                tools=["media_mimo_analysis"],
                tool_inputs={"media_mimo_analysis": {"capability": "fault_scene_analysis"}},
            )
            call = _tool_call(detail, "media_mimo_analysis") or {}
            data = ((call.get("output_json") or {}).get("data") or {})
            agent_results["media_mimo_analysis"] = {
                "run_id": (detail.get("run") or {}).get("run_id"),
                "tool_status": call.get("status"),
                "provider_mode": data.get("provider_mode"),
                "external_api_called": data.get("external_api_called"),
            }
    else:
        child_results["mimo"] = {"status": "blocked", "missing_or_invalid": missing_config("mimo")}

    if not missing_config("ocr_api"):
        child_results["ocr"] = _run_child("check_ocr_api_real_optional.py", base_url=args.base_url)
        media_id = child_results["ocr"].get("media_id")
        if child_results["ocr"].get("status") == "passed" and media_id:
            detail = _create_agent_run(
                token=token,
                base_url=args.base_url,
                agent_code="retrieval_qa_agent",
                media_id=media_id,
                tools=["media_ocr"],
                tool_inputs={"media_ocr": {"capability": "ocr"}},
            )
            call = _tool_call(detail, "media_ocr") or {}
            data = ((call.get("output_json") or {}).get("data") or {})
            agent_results["media_ocr"] = {
                "run_id": (detail.get("run") or {}).get("run_id"),
                "tool_status": call.get("status"),
                "provider_mode": data.get("provider_mode"),
                "external_api_called": data.get("external_api_called"),
            }
    else:
        child_results["ocr"] = {"status": "blocked", "missing_or_invalid": missing_config("ocr_api")}

    if not missing_config("cloud_llm"):
        child_results["cloud_llm"] = _run_child("check_cloud_llm_real_optional.py", base_url=args.base_url)
        if child_results["cloud_llm"].get("status") == "passed":
            detail = _create_agent_run(
                token=token,
                base_url=args.base_url,
                agent_code="retrieval_qa_agent",
                tools=["model_gateway_chat"],
                tool_inputs={
                    "model_gateway_chat": {
                        "provider": "cloud_openai",
                        "real_run": True,
                        "task_type": "general",
                        "prompt": f"{MARKER} agent tool cloud LLM integration check for PV inverter maintenance.",
                    }
                },
            )
            call = _tool_call(detail, "model_gateway_chat") or {}
            data = ((call.get("output_json") or {}).get("data") or {})
            agent_results["model_gateway_chat"] = {
                "run_id": (detail.get("run") or {}).get("run_id"),
                "tool_status": call.get("status"),
                "provider_mode": data.get("provider_mode"),
                "provider": data.get("provider"),
                "external_api_called": data.get("external_api_called"),
            }
    else:
        child_results["cloud_llm"] = {"status": "blocked", "missing_or_invalid": missing_config("cloud_llm")}

    real_agent_checks = [
        item for item in agent_results.values() if item.get("provider_mode") == "real" and item.get("external_api_called") is True
    ]
    failed_children = [name for name, item in child_results.items() if item.get("status") == "failed"]
    status_value = "failed" if failed_children else "passed" if real_agent_checks else "blocked"
    result = {
        "status": status_value,
        "real_external_api_used": bool(real_agent_checks),
        "child_provider_results": child_results,
        "agent_results": agent_results,
        "provider_mode_fields": bool(agent_results),
        "formal_business_objects_created": False,
        "current_user": {"username": user.get("username"), "role": user.get("role")},
    }
    write_result("real_agent_provider_integration_result.json", result)
    print_result(result)
    return 0 if status_value in {"passed", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
