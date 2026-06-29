from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error, request


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
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(http_request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
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
        raise AssertionError(f"login {account.username} did not return token")
    return token


def reference_keys(items: list[dict[str, Any]]) -> list[tuple[Any, Any, Any]]:
    return [
        (item.get("document_id"), item.get("chunk_id"), item.get("chunk_index"))
        for item in items
    ]


def assert_model_log(base_url: str, token: str, trace_id: str) -> None:
    status, response = request_json(
        "GET",
        f"{base_url}/model-gateway/logs?keyword={trace_id}&page=1&page_size=5",
        token=token,
    )
    data = assert_success(f"model log {trace_id}", status, response)
    items = data.get("items") or []
    if not any(item.get("trace_id") == trace_id for item in items):
        raise AssertionError(f"model_call_logs does not contain trace_id {trace_id}")


def assert_record_detail(
    base_url: str,
    token: str,
    endpoint: str,
    trace_id: str,
    label: str,
) -> dict[str, Any]:
    status, response = request_json(
        "GET",
        f"{base_url}/{endpoint}/{trace_id}",
        token=token,
    )
    data = assert_success(label, status, response)
    if data.get("trace_id") != trace_id:
        raise AssertionError(f"{label} trace_id mismatch: {data}")
    return data


def retrieval_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "question": "华为 SUN2000 逆变器绝缘阻抗低告警后如何排查？",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "document_type": None,
        "fault_type": "low_insulation",
        "alarm_code": None,
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
        "fault_type": "low_insulation",
        "alarm_code": None,
        "fault_description": "雨后逆变器出现绝缘阻抗低告警，并网前更容易复现。",
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
        "fault_type": "low_insulation",
        "alarm_code": None,
        "maintenance_level": "level_2",
        "include_references": True,
    }
    payload.update(overrides)
    return payload


def main() -> int:
    base_url = os.getenv("MODEL_ENHANCEMENT_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
    admin = Account(
        os.getenv("MODEL_ENHANCEMENT_ADMIN_USERNAME", "admin"),
        os.getenv("MODEL_ENHANCEMENT_ADMIN_PASSWORD", "admin123456"),
    )
    viewer = Account(
        os.getenv("MODEL_ENHANCEMENT_VIEWER_USERNAME", "viewer_task10"),
        os.getenv("MODEL_ENHANCEMENT_VIEWER_PASSWORD", "viewer123456"),
    )

    admin_token = login(base_url, admin)
    model_trace_ids: list[str] = []

    status, response = request_json("POST", f"{base_url}/retrieval/query", token=admin_token, payload=retrieval_payload())
    retrieval_base = assert_success("retrieval original", status, response)
    if retrieval_base.get("model_enhanced") is not False:
        raise AssertionError("retrieval original should not be model_enhanced")

    status, response = request_json(
        "POST",
        f"{base_url}/retrieval/query",
        token=admin_token,
        payload=retrieval_payload(
            enable_model_enhancement=True,
            model_provider="rule_based",
            allow_model_fallback=True,
        ),
    )
    retrieval_model = assert_success("retrieval rule_based enhancement", status, response)
    if not retrieval_model.get("model_enhanced") or not retrieval_model.get("model_call_trace_id"):
        raise AssertionError(f"retrieval enhancement metadata missing: {retrieval_model}")
    if reference_keys(retrieval_model.get("references") or []) != reference_keys(retrieval_base.get("references") or []):
        raise AssertionError("retrieval references changed during enhancement")
    qa_record = assert_record_detail(
        base_url,
        admin_token,
        "retrieval/records",
        retrieval_model["trace_id"],
        "qa record detail",
    )
    if not qa_record.get("references") or not qa_record.get("suggested_steps"):
        raise AssertionError(f"qa record did not persist references or suggested_steps: {qa_record}")
    if qa_record.get("model_provider") != retrieval_model.get("model_provider"):
        raise AssertionError(f"qa record model_provider mismatch: {qa_record}")
    model_trace_ids.append(retrieval_model["model_call_trace_id"])

    for provider in ("local_llama_cpp", "cloud_openai"):
        status, response = request_json(
            "POST",
            f"{base_url}/retrieval/query",
            token=admin_token,
            payload=retrieval_payload(
                enable_model_enhancement=True,
                model_provider=provider,
                allow_model_fallback=True,
            ),
        )
        data = assert_success(f"retrieval {provider} fallback", status, response)
        if not data.get("fallback_used") or not data.get("model_call_trace_id"):
            raise AssertionError(f"retrieval {provider} fallback metadata missing: {data}")
        model_trace_ids.append(data["model_call_trace_id"])

    status, response = request_json("POST", f"{base_url}/diagnosis/analyze", token=admin_token, payload=diagnosis_payload())
    diagnosis_base = assert_success("diagnosis original", status, response)
    if diagnosis_base.get("model_enhanced") is not False:
        raise AssertionError("diagnosis original should not be model_enhanced")

    status, response = request_json(
        "POST",
        f"{base_url}/diagnosis/analyze",
        token=admin_token,
        payload=diagnosis_payload(
            enable_model_enhancement=True,
            model_provider="rule_based",
            allow_model_fallback=True,
        ),
    )
    diagnosis_model = assert_success("diagnosis rule_based enhancement", status, response)
    if not diagnosis_model.get("model_enhanced") or not diagnosis_model.get("model_call_trace_id"):
        raise AssertionError(f"diagnosis enhancement metadata missing: {diagnosis_model}")
    if reference_keys(diagnosis_model.get("references") or []) != reference_keys(diagnosis_base.get("references") or []):
        raise AssertionError("diagnosis references changed during enhancement")
    diagnosis_record = assert_record_detail(
        base_url,
        admin_token,
        "diagnosis/records",
        diagnosis_model["trace_id"],
        "diagnosis record detail",
    )
    if diagnosis_record.get("model_provider") != diagnosis_model.get("model_provider"):
        raise AssertionError(f"diagnosis record model_provider mismatch: {diagnosis_record}")
    if not diagnosis_record.get("safety_notes") or not diagnosis_record.get("recommended_actions"):
        raise AssertionError(f"diagnosis record did not persist safety_notes or recommended_actions: {diagnosis_record}")
    model_trace_ids.append(diagnosis_model["model_call_trace_id"])

    status, response = request_json("POST", f"{base_url}/sop/generate", token=admin_token, payload=sop_payload())
    sop_base = assert_success("sop original", status, response)
    if sop_base.get("model_enhanced") is not False:
        raise AssertionError("sop original should not be model_enhanced")

    status, response = request_json(
        "POST",
        f"{base_url}/sop/generate",
        token=admin_token,
        payload=sop_payload(
            enable_model_enhancement=True,
            model_provider="rule_based",
            allow_model_fallback=True,
        ),
    )
    sop_model = assert_success("sop rule_based enhancement", status, response)
    if not sop_model.get("model_enhanced") or not sop_model.get("model_call_trace_id"):
        raise AssertionError(f"sop enhancement metadata missing: {sop_model}")
    if reference_keys(sop_model.get("references") or []) != reference_keys(sop_base.get("references") or []):
        raise AssertionError("sop references changed during enhancement")
    if len(sop_model.get("steps") or []) != len(sop_base.get("steps") or []):
        raise AssertionError("sop steps changed during enhancement")
    model_trace_ids.append(sop_model["model_call_trace_id"])

    for provider in ("local_llama_cpp", "cloud_openai"):
        status, response = request_json(
            "POST",
            f"{base_url}/sop/generate",
            token=admin_token,
            payload=sop_payload(
                enable_model_enhancement=True,
                model_provider=provider,
                allow_model_fallback=True,
            ),
        )
        data = assert_success(f"sop {provider} fallback", status, response)
        if not data.get("fallback_used") or not data.get("model_call_trace_id"):
            raise AssertionError(f"sop {provider} fallback metadata missing: {data}")
        model_trace_ids.append(data["model_call_trace_id"])

    for trace_id in model_trace_ids:
        assert_model_log(base_url, admin_token, trace_id)

    api_key = os.getenv("CLOUD_LLM_API_KEY", "")
    if api_key:
        status, response = request_json(
            "GET",
            f"{base_url}/model-gateway/logs?keyword={model_trace_ids[0]}&page=1&page_size=1",
            token=admin_token,
        )
        data = assert_success("api key exposure check", status, response)
        if api_key in json.dumps(data, ensure_ascii=False):
            raise AssertionError("CLOUD_LLM_API_KEY was exposed in log response")

    try:
        viewer_token = login(base_url, viewer)
    except AssertionError as exc:
        print(f"[skipped] viewer retrieval enhancement check: {exc}")
    else:
        status, response = request_json(
            "POST",
            f"{base_url}/retrieval/query",
            token=viewer_token,
            payload=retrieval_payload(
                enable_model_enhancement=True,
                model_provider="cloud_openai",
                allow_model_fallback=True,
            ),
        )
        data = assert_success("viewer retrieval cloud request uses safe fallback", status, response)
        if data.get("model_provider") != "rule_based" or not data.get("fallback_used"):
            raise AssertionError(f"viewer cloud request was not safely routed to rule_based fallback: {data}")

    print("[passed] model enhancement trace ids:", ", ".join(model_trace_ids))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
