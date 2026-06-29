from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from app.core.config import get_settings


BASE_URL = os.getenv("CLOUD_MODEL_ONLINE_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")


@dataclass(slots=True)
class CheckResult:
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
            parsed = json.loads(body) if body else {"message": exc.reason}
        except json.JSONDecodeError:
            parsed = {"message": body[:500], "data": None}
        return exc.code, parsed


def api_data(label: str, status: int, response: dict[str, Any]) -> Any:
    if status >= 400 or response.get("code") not in (0, 200):
        raise AssertionError(f"{label} failed: http={status}, message={response.get('message')}")
    return response.get("data")


def login() -> str:
    username = os.getenv("CLOUD_MODEL_ONLINE_ADMIN_USERNAME") or os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
    password = os.getenv("CLOUD_MODEL_ONLINE_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
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


def config_mode() -> tuple[str, dict[str, Any]]:
    settings = get_settings()
    missing: list[str] = []
    if not settings.CLOUD_LLM_ENABLED:
        missing.append("CLOUD_LLM_ENABLED=true")
    if not settings.CLOUD_LLM_BASE_URL:
        missing.append("CLOUD_LLM_BASE_URL")
    if not settings.CLOUD_LLM_API_KEY:
        missing.append("CLOUD_LLM_API_KEY")
    if not settings.CLOUD_LLM_MODEL:
        missing.append("CLOUD_LLM_MODEL")
    mode = "blocked" if missing else "online"
    return mode, {
        "cloud_enabled": settings.CLOUD_LLM_ENABLED,
        "base_url_configured": bool(settings.CLOUD_LLM_BASE_URL),
        "api_key_configured": bool(settings.CLOUD_LLM_API_KEY),
        "model_configured": bool(settings.CLOUD_LLM_MODEL),
        "model": settings.CLOUD_LLM_MODEL or None,
        "timeout_seconds": settings.CLOUD_LLM_TIMEOUT_SECONDS,
        "max_tokens": settings.CLOUD_LLM_MAX_TOKENS,
        "missing": missing,
    }


def provider_status(token: str) -> dict[str, Any]:
    status, response = request_json("GET", f"{BASE_URL}/model-gateway/status", token=token)
    data = api_data("model-gateway/status", status, response)
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, list):
        raise AssertionError("model-gateway/status did not return providers")
    for provider in providers:
        if provider.get("provider") == "cloud_openai":
            print(
                "[info] cloud_openai status="
                f"{provider.get('availability_status')} configured={provider.get('configured')} "
                f"api_key_configured={provider.get('api_key_configured')}"
            )
            return provider
    raise AssertionError("cloud_openai provider missing from status")


def assert_no_secret(label: str, payload: Any) -> None:
    settings = get_settings()
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    if settings.CLOUD_LLM_API_KEY and settings.CLOUD_LLM_API_KEY in serialized:
        raise AssertionError(f"{label} exposed CLOUD_LLM_API_KEY")
    if "Authorization" in serialized or "Bearer " in serialized:
        raise AssertionError(f"{label} exposed Authorization header")
    print(f"[passed] {label} secret safety")


def model_gateway_call(token: str, endpoint: str, *, allow_fallback: bool, expect_cloud: bool) -> str:
    payload = {
        "provider": "cloud_openai",
        "task_type": "qa",
        "allow_fallback": allow_fallback,
        "messages": [
            {
                "role": "system",
                "content": "You are a PV inverter maintenance assistant. Do not invent traceable sources.",
            },
            {
                "role": "user",
                "content": "Give one safety-aware sentence for Huawei SUN2000 low insulation alarm inspection.",
            },
        ],
    }
    status, response = request_json("POST", f"{BASE_URL}/model-gateway/{endpoint}", token=token, payload=payload)
    data = api_data(f"model-gateway/{endpoint}", status, response)
    assert_no_secret(f"model-gateway/{endpoint} response", data)
    trace_id = data.get("trace_id")
    if not trace_id:
        raise AssertionError(f"model-gateway/{endpoint} did not return trace_id")
    if expect_cloud:
        if data.get("provider") != "cloud_openai" or data.get("fallback_used"):
            raise AssertionError(f"model-gateway/{endpoint} did not complete real cloud call")
        if not data.get("content"):
            raise AssertionError(f"model-gateway/{endpoint} returned empty cloud content")
        print(f"[passed] model-gateway/{endpoint} real cloud trace_id={trace_id}")
    else:
        if data.get("provider") != "rule_based" or not data.get("fallback_used"):
            raise AssertionError(f"model-gateway/{endpoint} did not use rule_based fallback in blocked mode")
        print(f"[blocked] model-gateway/{endpoint} used fallback trace_id={trace_id}")
    return trace_id


def business_payloads(allow_fallback: bool) -> list[tuple[str, dict[str, Any]]]:
    model_options = {
        "enable_model_enhancement": True,
        "model_provider": "cloud_openai",
        "allow_model_fallback": allow_fallback,
        "enable_kg_enhancement": True,
    }
    return [
        (
            "retrieval/query",
            {
                **model_options,
                "question": "Huawei SUN2000 low insulation resistance alarm inspection steps",
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "device_type": "pv_inverter",
                "document_type": "manual",
                "fault_type": "low_insulation_resistance",
                "top_k": 5,
                "include_history": True,
            },
        ),
        (
            "diagnosis/analyze",
            {
                **model_options,
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "model": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
                "fault_description": "SUN2000 reports low insulation resistance after rainy weather.",
                "observed_symptoms": ["alarm appears before grid connection", "wet environment"],
                "media_ids": [],
                "include_history": True,
            },
        ),
        (
            "sop/generate",
            {
                **model_options,
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "model": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
                "maintenance_level": "level_2",
                "include_references": True,
            },
        ),
    ]


def business_call(token: str, endpoint: str, payload: dict[str, Any], *, expect_cloud: bool) -> str:
    status, response = request_json("POST", f"{BASE_URL}/{endpoint}", token=token, payload=payload)
    data = api_data(endpoint, status, response)
    assert_no_secret(f"{endpoint} response", data)
    trace_id = data.get("model_call_trace_id")
    if not trace_id:
        raise AssertionError(f"{endpoint} did not return model_call_trace_id")
    if expect_cloud:
        if data.get("model_provider") != "cloud_openai" or data.get("fallback_used"):
            raise AssertionError(f"{endpoint} did not use real cloud enhancement")
        print(f"[passed] {endpoint} real cloud enhancement trace_id={trace_id}")
    else:
        if data.get("model_provider") != "rule_based" or not data.get("fallback_used"):
            raise AssertionError(f"{endpoint} did not use fallback in blocked mode")
        print(f"[blocked] {endpoint} used fallback trace_id={trace_id}")
    return trace_id


def log_detail(token: str, trace_id: str) -> dict[str, Any]:
    keyword = parse.quote(trace_id)
    status, response = request_json(
        "GET",
        f"{BASE_URL}/model-gateway/logs?keyword={keyword}&page=1&page_size=10",
        token=token,
    )
    data = api_data(f"logs list {trace_id}", status, response)
    assert_no_secret(f"logs list {trace_id}", data)
    items = data.get("items") if isinstance(data, dict) else []
    match = next((item for item in items or [] if item.get("trace_id") == trace_id), None)
    if not match:
        raise AssertionError(f"model_call_logs missing trace_id {trace_id}")
    status, response = request_json("GET", f"{BASE_URL}/model-gateway/logs/{match['id']}", token=token)
    detail = api_data(f"logs detail {trace_id}", status, response)
    assert_no_secret(f"logs detail {trace_id}", detail)
    return detail


def assert_prompt_context(detail: dict[str, Any]) -> None:
    prompt = detail.get("prompt") or ""
    if "Approved knowledge graph context:" not in prompt:
        raise AssertionError("model prompt did not include KG context boundary")
    if "Media metadata context:" not in prompt:
        raise AssertionError("model prompt did not include media metadata boundary")
    if "Do not include local file paths or binary image data." not in prompt:
        raise AssertionError("model prompt did not include media/file safety rule")
    print("[passed] prompt includes KG and media safety context")


def run() -> CheckResult:
    mode, report = config_mode()
    print(json.dumps({"cloud_configuration": report, "mode": mode}, ensure_ascii=False, indent=2))
    token = login()
    initial_status = provider_status(token)

    if mode == "blocked":
        if initial_status.get("configured"):
            raise AssertionError("local settings are blocked but provider status reports configured")
        expect_cloud = False
        allow_fallback = True
    else:
        if not initial_status.get("enabled") or not initial_status.get("configured"):
            raise AssertionError("cloud provider is not enabled/configured")
        expect_cloud = True
        allow_fallback = False

    gateway_traces = [
        model_gateway_call(token, "test", allow_fallback=allow_fallback, expect_cloud=expect_cloud),
        model_gateway_call(token, "chat", allow_fallback=allow_fallback, expect_cloud=expect_cloud),
    ]
    business_traces: list[str] = []

    for endpoint, payload in business_payloads(allow_fallback):
        business_traces.append(business_call(token, endpoint, payload, expect_cloud=expect_cloud))

    traces = gateway_traces + business_traces
    details = [log_detail(token, trace_id) for trace_id in traces]
    business_trace_set = set(business_traces)
    business_details = [detail for detail in details if detail.get("trace_id") in business_trace_set]
    if business_details:
        assert_prompt_context(business_details[0])

    final_status = provider_status(token)
    if expect_cloud and final_status.get("availability_status") != "available":
        raise AssertionError("cloud provider status did not become available after real cloud calls")
    return CheckResult(
        mode="passed" if expect_cloud else "blocked",
        traces=traces,
        notes=[
            "real cloud call completed" if expect_cloud else "cloud credentials missing or disabled; fallback verified",
            f"final_cloud_status={final_status.get('availability_status')}",
        ],
    )


def main() -> int:
    result = run()
    print(
        json.dumps(
            {"result": {"mode": result.mode, "traces": result.traces, "notes": result.notes}},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.mode in {"passed", "blocked"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
