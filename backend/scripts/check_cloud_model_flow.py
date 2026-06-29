from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from app.core.config import get_settings


@dataclass(slots=True)
class Account:
    username: str
    password: str


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
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
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"code": exc.code, "message": body, "data": None}
        return exc.code, parsed


def assert_success(label: str, status: int, response: dict[str, Any]) -> dict[str, Any]:
    if status >= 400 or response.get("code") not in (0, 200):
        raise AssertionError(f"{label} failed: http={status}, response={response}")
    data = response.get("data")
    if data is None:
        raise AssertionError(f"{label} returned empty data")
    print(f"[passed] {label}")
    return data


def login(base_url: str, account: Account) -> str:
    status, response = request_json(
        "POST",
        f"{base_url}/auth/login",
        payload={"username": account.username, "password": account.password},
    )
    data = assert_success(f"login {account.username}", status, response)
    token = data.get("access_token")
    if not token:
        raise AssertionError(f"login {account.username} did not return access_token")
    return token


def secret_status(value: str) -> str:
    if not value:
        return "not_configured"
    return "configured"


def cloud_config_report() -> dict[str, Any]:
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
    return {
        "enabled": settings.CLOUD_LLM_ENABLED,
        "base_url_configured": bool(settings.CLOUD_LLM_BASE_URL),
        "api_key": secret_status(settings.CLOUD_LLM_API_KEY),
        "model": settings.CLOUD_LLM_MODEL or None,
        "api_type": settings.CLOUD_LLM_API_TYPE,
        "missing": missing,
        "cloud_real_call": "blocked" if missing else "ready",
    }


def get_cloud_provider(status_payload: dict[str, Any]) -> dict[str, Any]:
    providers = status_payload.get("providers") or []
    for provider in providers:
        if provider.get("provider") == "cloud_openai":
            return provider
    raise AssertionError("model-gateway/status did not include cloud_openai provider")


def assert_no_secret(label: str, payload: Any, secret: str) -> None:
    if not secret:
        return
    serialized = json.dumps(payload, ensure_ascii=False)
    if secret in serialized:
        raise AssertionError(f"{label} exposed CLOUD_LLM_API_KEY")
    print(f"[passed] {label} did not expose CLOUD_LLM_API_KEY")


def assert_model_log(base_url: str, token: str, trace_id: str, secret: str) -> None:
    keyword = parse.quote(trace_id)
    status, response = request_json(
        "GET",
        f"{base_url}/model-gateway/logs?keyword={keyword}&page=1&page_size=5",
        token=token,
    )
    data = assert_success(f"model logs contain {trace_id}", status, response)
    items = data.get("items") or []
    matching = [item for item in items if item.get("trace_id") == trace_id]
    if not matching:
        raise AssertionError(f"model_call_logs does not contain trace_id {trace_id}")
    assert_no_secret(f"model log list {trace_id}", data, secret)

    log_id = matching[0].get("id")
    if not log_id:
        raise AssertionError(f"model_call_logs row missing id for trace_id {trace_id}")
    status, response = request_json("GET", f"{base_url}/model-gateway/logs/{log_id}", token=token)
    detail = assert_success(f"model log detail {trace_id}", status, response)
    assert_no_secret(f"model log detail {trace_id}", detail, secret)


def retrieval_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "question": "华为 SUN2000 光伏逆变器绝缘阻抗低告警后如何排查？",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "document_type": "manual",
        "fault_type": "low_insulation_resistance",
        "top_k": 5,
        "include_history": True,
    }
    payload.update(overrides)
    return payload


def diagnosis_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "fault_description": "雨后华为 SUN2000 光伏逆变器出现绝缘阻抗低告警，并网前更容易复现。",
        "observed_symptoms": ["雨后高湿环境复现", "并网前提示绝缘异常"],
        "media_ids": [],
        "include_history": True,
    }
    payload.update(overrides)
    return payload


def sop_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "maintenance_level": "level_2",
        "include_references": True,
    }
    payload.update(overrides)
    return payload


def assert_fallback_result(label: str, data: dict[str, Any]) -> str:
    if data.get("provider") != "rule_based" or data.get("requested_provider") != "cloud_openai":
        raise AssertionError(f"{label} did not route to rule_based fallback: {data}")
    if not data.get("fallback_used"):
        raise AssertionError(f"{label} did not mark fallback_used=true: {data}")
    trace_id = data.get("trace_id")
    if not trace_id:
        raise AssertionError(f"{label} did not return trace_id")
    print(f"[passed] {label} fallback trace_id={trace_id}")
    return trace_id


def assert_cloud_result(label: str, data: dict[str, Any]) -> str:
    if data.get("provider") != "cloud_openai":
        raise AssertionError(f"{label} did not use cloud_openai: {data}")
    if data.get("fallback_used"):
        raise AssertionError(f"{label} unexpectedly used fallback: {data}")
    if not data.get("content"):
        raise AssertionError(f"{label} returned empty content: {data}")
    trace_id = data.get("trace_id")
    if not trace_id:
        raise AssertionError(f"{label} did not return trace_id")
    print(f"[passed] {label} real cloud trace_id={trace_id}")
    return trace_id


def assert_business_model_trace(label: str, data: dict[str, Any], *, expect_cloud: bool) -> str:
    trace_id = data.get("model_call_trace_id")
    if not trace_id:
        raise AssertionError(f"{label} did not return model_call_trace_id: {data}")
    if expect_cloud:
        if data.get("model_provider") != "cloud_openai" or data.get("fallback_used"):
            raise AssertionError(f"{label} did not use real cloud model: {data}")
    else:
        if data.get("model_provider") != "rule_based" or not data.get("fallback_used"):
            raise AssertionError(f"{label} did not safely fallback to rule_based: {data}")
    print(f"[passed] {label} model_call_trace_id={trace_id}")
    return trace_id


def run_gateway_checks(base_url: str, token: str, *, blocked: bool, secret: str) -> list[str]:
    traces: list[str] = []
    allow_fallback = blocked

    status, response = request_json(
        "POST",
        f"{base_url}/model-gateway/test",
        token=token,
        payload={
            "provider": "cloud_openai",
            "task_type": "qa",
            "allow_fallback": allow_fallback,
            "prompt": "请用中文说明华为 SUN2000 光伏逆变器绝缘阻抗低告警的安全排查边界。",
        },
    )
    data = assert_success("model-gateway/test cloud_openai", status, response)
    traces.append(assert_fallback_result("model-gateway/test", data) if blocked else assert_cloud_result("model-gateway/test", data))

    status, response = request_json(
        "POST",
        f"{base_url}/model-gateway/chat",
        token=token,
        payload={
            "provider": "cloud_openai",
            "task_type": "qa",
            "allow_fallback": allow_fallback,
            "trace_source": "task_14b_cloud_model_flow",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a maintenance assistant for Huawei and Sungrow PV inverters.",
                },
                {
                    "role": "user",
                    "content": "请给出阳光电源 SG 系列逆变器通信中断告警的初步排查边界。",
                },
            ],
        },
    )
    data = assert_success("model-gateway/chat cloud_openai", status, response)
    traces.append(assert_fallback_result("model-gateway/chat", data) if blocked else assert_cloud_result("model-gateway/chat", data))

    for trace_id in traces:
        assert_model_log(base_url, token, trace_id, secret)
    return traces


def run_business_checks(base_url: str, token: str, *, blocked: bool, secret: str) -> list[str]:
    traces: list[str] = []
    model_options = {
        "enable_model_enhancement": True,
        "model_provider": "cloud_openai",
        "allow_model_fallback": blocked,
    }

    status, response = request_json(
        "POST",
        f"{base_url}/retrieval/query",
        token=token,
        payload=retrieval_payload(**model_options),
    )
    retrieval = assert_success("retrieval cloud enhancement", status, response)
    traces.append(assert_business_model_trace("retrieval", retrieval, expect_cloud=not blocked))
    if retrieval.get("references"):
        print(f"[info] retrieval references count={len(retrieval.get('references') or [])}")
    else:
        print("[info] retrieval references count=0; this may be expected if no matching knowledge chunks exist")

    status, response = request_json(
        "POST",
        f"{base_url}/diagnosis/analyze",
        token=token,
        payload=diagnosis_payload(**model_options),
    )
    diagnosis = assert_success("diagnosis cloud enhancement", status, response)
    traces.append(assert_business_model_trace("diagnosis", diagnosis, expect_cloud=not blocked))

    status, response = request_json(
        "POST",
        f"{base_url}/sop/generate",
        token=token,
        payload=sop_payload(**model_options),
    )
    sop = assert_success("sop cloud enhancement", status, response)
    traces.append(assert_business_model_trace("sop", sop, expect_cloud=not blocked))
    if len(sop.get("steps") or []) == 0:
        raise AssertionError(f"sop returned no steps: {sop}")

    for trace_id in traces:
        assert_model_log(base_url, token, trace_id, secret)
    return traces


def main() -> int:
    base_url = os.getenv("CLOUD_MODEL_FLOW_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
    admin = Account(
        os.getenv("CLOUD_MODEL_FLOW_ADMIN_USERNAME", "admin"),
        os.getenv("CLOUD_MODEL_FLOW_ADMIN_PASSWORD", "admin123456"),
    )

    config = cloud_config_report()
    print(json.dumps({"cloud_config": config}, ensure_ascii=False, indent=2))
    blocked = config["cloud_real_call"] == "blocked"

    token = login(base_url, admin)
    status, response = request_json("GET", f"{base_url}/model-gateway/status", token=token)
    gateway_status = assert_success("model-gateway/status", status, response)
    cloud_provider = get_cloud_provider(gateway_status)
    print(json.dumps({"cloud_provider_status": cloud_provider}, ensure_ascii=False, indent=2))

    if blocked:
        if cloud_provider.get("enabled") and cloud_provider.get("configured"):
            raise AssertionError(f"cloud provider looks configured but local config is blocked: {cloud_provider}")
        print("[blocked] real cloud call skipped because CLOUD_LLM_* is not fully configured")
    else:
        if not cloud_provider.get("enabled") or not cloud_provider.get("configured"):
            raise AssertionError(f"cloud provider is not enabled/configured: {cloud_provider}")
        print("[info] real cloud call will be attempted")

    settings = get_settings()
    secret = settings.CLOUD_LLM_API_KEY
    traces: list[str] = []
    traces.extend(run_gateway_checks(base_url, token, blocked=blocked, secret=secret))
    traces.extend(run_business_checks(base_url, token, blocked=blocked, secret=secret))

    result = {
        "cloud_real_call": "blocked" if blocked else "passed",
        "trace_ids_checked": traces,
        "api_key_exposure": "checked" if secret else "not_applicable",
    }
    print(json.dumps({"result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
