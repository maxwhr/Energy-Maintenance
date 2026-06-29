from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from app.core.config import get_settings


BASE_URL = os.getenv("LOCAL_LLAMA_CPP_FLOW_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")


@dataclass(slots=True)
class FlowResult:
    mode: str
    traces: list[str]
    notes: list[str]


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 90,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {"message": exc.reason, "data": None}
        except json.JSONDecodeError:
            parsed = {"message": body[:500], "data": None}
        return exc.code, parsed


def api_data(label: str, status: int, response: dict[str, Any]) -> Any:
    if status >= 400 or response.get("code") not in (0, 200):
        raise AssertionError(f"{label} failed: http={status}, message={response.get('message')}")
    data = response.get("data")
    if data is None:
        raise AssertionError(f"{label} returned empty data")
    return data


def login() -> str:
    username = os.getenv("LOCAL_LLAMA_CPP_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
    password = os.getenv("LOCAL_LLAMA_CPP_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
    status, response = request_json(
        "POST",
        f"{BASE_URL}/auth/login",
        payload={"username": username, "password": password},
    )
    data = api_data("admin login", status, response)
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise AssertionError("admin login did not return access_token")
    print("[passed] admin login")
    return token


def local_config_report() -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.LOCAL_LLM_ENABLED,
        "base_url_configured": bool(settings.LOCAL_LLM_BASE_URL),
        "model_configured": bool(settings.LOCAL_LLM_MODEL),
        "api_type": settings.LOCAL_LLM_API_TYPE,
        "health_path": settings.LOCAL_LLM_HEALTH_PATH,
        "timeout_seconds": settings.LOCAL_LLM_TIMEOUT_SECONDS,
        "max_tokens": settings.LOCAL_LLM_MAX_TOKENS,
    }


def get_local_provider(token: str) -> dict[str, Any]:
    status, response = request_json("GET", f"{BASE_URL}/model-gateway/status", token=token)
    data = api_data("model-gateway/status", status, response)
    providers = data.get("providers") if isinstance(data, dict) else []
    for provider in providers or []:
        if provider.get("provider") == "local_llama_cpp":
            print(
                "[info] local_llama_cpp status="
                f"{provider.get('availability_status')} enabled={provider.get('enabled')} "
                f"configured={provider.get('configured')}"
            )
            return provider
    raise AssertionError("local_llama_cpp provider missing from model-gateway/status")


def assert_no_local_path(label: str, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    if ".gguf" in serialized and (":\\" in serialized or "/" in serialized):
        raise AssertionError(f"{label} appears to expose a full GGUF path")
    if "Authorization" in serialized or "Bearer " in serialized:
        raise AssertionError(f"{label} exposed Authorization header")
    print(f"[passed] {label} path/header safety")


def gateway_call(token: str, *, allow_fallback: bool, expect_local: bool, endpoint: str) -> str:
    payload = {
        "provider": "local_llama_cpp",
        "task_type": "qa",
        "allow_fallback": allow_fallback,
        "messages": [
            {
                "role": "system",
                "content": "You are a PV inverter maintenance assistant. Do not invent traceable sources.",
            },
            {
                "role": "user",
                "content": "Give one concise safety reminder for Huawei SUN2000 maintenance.",
            },
        ],
    }
    status, response = request_json(
        "POST",
        f"{BASE_URL}/model-gateway/{endpoint}",
        token=token,
        payload=payload,
    )
    data = api_data(f"model-gateway/{endpoint}", status, response)
    assert_no_local_path(f"model-gateway/{endpoint} response", data)
    trace_id = data.get("trace_id")
    if not trace_id:
        raise AssertionError(f"model-gateway/{endpoint} did not return trace_id")
    if expect_local:
        if data.get("provider") != "local_llama_cpp" or data.get("fallback_used"):
            raise AssertionError(f"model-gateway/{endpoint} did not use real local llama.cpp")
        if not data.get("content"):
            raise AssertionError(f"model-gateway/{endpoint} returned empty content")
        print(f"[passed] model-gateway/{endpoint} real local trace_id={trace_id}")
    else:
        if data.get("provider") != "rule_based" or not data.get("fallback_used"):
            raise AssertionError(f"model-gateway/{endpoint} did not use rule_based fallback in blocked mode")
        print(f"[blocked] model-gateway/{endpoint} used fallback trace_id={trace_id}")
    return trace_id


def gateway_failure_call(token: str, *, endpoint: str) -> str:
    payload = {
        "provider": "local_llama_cpp",
        "task_type": "qa",
        "allow_fallback": False,
        "prompt": "Check local llama.cpp failure path without fallback.",
    }
    status, response = request_json(
        "POST",
        f"{BASE_URL}/model-gateway/{endpoint}",
        token=token,
        payload=payload,
    )
    data = api_data(f"model-gateway/{endpoint} no-fallback", status, response)
    assert_no_local_path(f"model-gateway/{endpoint} no-fallback response", data)
    trace_id = data.get("trace_id")
    if not trace_id:
        raise AssertionError(f"model-gateway/{endpoint} no-fallback did not return trace_id")
    if data.get("provider") != "local_llama_cpp" or data.get("success") or data.get("fallback_used"):
        raise AssertionError(f"model-gateway/{endpoint} no-fallback did not return a clear local failure")
    if not data.get("error_message"):
        raise AssertionError(f"model-gateway/{endpoint} no-fallback did not return error_message")
    print(f"[blocked] model-gateway/{endpoint} no-fallback failed clearly trace_id={trace_id}")
    return trace_id


def log_detail(token: str, trace_id: str) -> dict[str, Any]:
    keyword = parse.quote(trace_id)
    status, response = request_json(
        "GET",
        f"{BASE_URL}/model-gateway/logs?keyword={keyword}&page=1&page_size=10",
        token=token,
    )
    data = api_data(f"logs list {trace_id}", status, response)
    assert_no_local_path(f"logs list {trace_id}", data)
    items = data.get("items") if isinstance(data, dict) else []
    match = next((item for item in items or [] if item.get("trace_id") == trace_id), None)
    if not match:
        raise AssertionError(f"model_call_logs missing trace_id {trace_id}")
    status, response = request_json("GET", f"{BASE_URL}/model-gateway/logs/{match['id']}", token=token)
    detail = api_data(f"logs detail {trace_id}", status, response)
    assert_no_local_path(f"logs detail {trace_id}", detail)
    return detail


def business_call(token: str, *, expect_local: bool, allow_fallback: bool) -> str:
    payload = {
        "question": "Huawei SUN2000 low insulation resistance alarm inspection steps",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "document_type": "manual",
        "fault_type": "low_insulation_resistance",
        "top_k": 5,
        "enable_kg_enhancement": True,
        "enable_model_enhancement": True,
        "model_provider": "local_llama_cpp",
        "allow_model_fallback": allow_fallback,
    }
    status, response = request_json("POST", f"{BASE_URL}/retrieval/query", token=token, payload=payload)
    data = api_data("retrieval local model enhancement", status, response)
    assert_no_local_path("retrieval response", data)
    trace_id = data.get("model_call_trace_id")
    if not trace_id:
        raise AssertionError("retrieval response did not include model_call_trace_id")
    if expect_local:
        if data.get("model_provider") != "local_llama_cpp" or data.get("fallback_used"):
            raise AssertionError("retrieval did not use real local llama.cpp")
        print(f"[passed] retrieval real local model trace_id={trace_id}")
    else:
        if data.get("model_provider") != "rule_based" or not data.get("fallback_used"):
            raise AssertionError("retrieval did not use fallback in blocked mode")
        print(f"[blocked] retrieval used fallback trace_id={trace_id}")
    return trace_id


def run() -> FlowResult:
    print(json.dumps({"local_configuration": local_config_report()}, ensure_ascii=False, indent=2))
    token = login()
    local_provider = get_local_provider(token)
    available = bool(local_provider.get("enabled") and local_provider.get("configured") and local_provider.get("available"))
    mode = "passed" if available else "blocked"
    allow_fallback = not available

    traces: list[str] = []
    if available:
        traces.append(gateway_call(token, allow_fallback=False, expect_local=True, endpoint="test"))
        traces.append(gateway_call(token, allow_fallback=False, expect_local=True, endpoint="chat"))
        traces.append(business_call(token, expect_local=True, allow_fallback=False))
        traces.append(gateway_call(token, allow_fallback=True, expect_local=True, endpoint="test"))
    else:
        traces.append(gateway_failure_call(token, endpoint="test"))
        traces.append(gateway_failure_call(token, endpoint="chat"))
        traces.append(gateway_call(token, allow_fallback=True, expect_local=False, endpoint="test"))
        traces.append(gateway_call(token, allow_fallback=True, expect_local=False, endpoint="chat"))
        traces.append(business_call(token, expect_local=False, allow_fallback=True))

    for trace_id in traces:
        log_detail(token, trace_id)

    notes = [
        f"local_availability_status={local_provider.get('availability_status')}",
        "real local llama.cpp call completed" if available else "local llama.cpp service unavailable or disabled; fallback verified",
    ]
    return FlowResult(mode=mode, traces=traces, notes=notes)


def main() -> int:
    result = run()
    print(
        json.dumps(
            {"result": {"mode": result.mode, "traces": result.traces, "notes": result.notes}},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
