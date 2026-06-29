from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any
from urllib import error, request


@dataclass(slots=True)
class CheckResult:
    name: str
    method: str
    path: str
    passed: bool
    status: int | None
    message: str
    trace_id: str | None = None


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
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"code": exc.code, "message": body, "data": None}
        return exc.code, parsed


def is_success(status: int, response: dict[str, Any]) -> bool:
    return status < 400 and response.get("code") in (0, 200)


def run_check(
    results: list[CheckResult],
    base_url: str,
    name: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    url = f"{base_url}{path}"
    try:
        status, response = request_json(method, url, token=token, payload=payload)
    except Exception as exc:  # noqa: BLE001 - smoke script should report any failure plainly.
        results.append(CheckResult(name, method, path, False, None, str(exc)))
        return None

    passed = is_success(status, response)
    data = response.get("data") if isinstance(response, dict) else None
    trace_id = data.get("trace_id") if isinstance(data, dict) else None
    message = response.get("message", "") if isinstance(response, dict) else ""
    results.append(CheckResult(name, method, path, passed, status, message, trace_id))
    return data if passed and isinstance(data, dict) else None


def main() -> int:
    base_url = os.getenv("FULL_SMOKE_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
    username = os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin")
    password = os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")
    results: list[CheckResult] = []

    run_check(results, base_url, "health", "GET", "/health")
    run_check(results, base_url, "system_status", "GET", "/system/status")

    login_data = run_check(
        results,
        base_url,
        "login_admin",
        "POST",
        "/auth/login",
        payload={"username": username, "password": password},
    )
    token = login_data.get("access_token") if login_data else None
    if not token:
        print(json.dumps({"status": "failed", "results": [asdict(item) for item in results]}, ensure_ascii=False, indent=2))
        return 1

    run_check(results, base_url, "system_statistics", "GET", "/system/statistics", token=token)
    run_check(results, base_url, "devices", "GET", "/devices?page=1&page_size=5", token=token)
    run_check(results, base_url, "knowledge_documents", "GET", "/knowledge/documents?page=1&page_size=5", token=token)

    retrieval_payload = {
        "question": "Task14A_Smoke 华为 SUN2000 逆变器绝缘阻抗低告警后如何排查？",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation",
        "top_k": 3,
        "include_history": True,
        "enable_model_enhancement": False,
    }
    run_check(results, base_url, "retrieval_query", "POST", "/retrieval/query", token=token, payload=retrieval_payload)

    diagnosis_payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation",
        "fault_description": "Task14A_Smoke 雨后出现绝缘阻抗低告警，现场需要复核直流侧绝缘和接插件状态。",
        "observed_symptoms": ["Task14A_Smoke", "雨后高湿环境复现"],
        "media_ids": [],
        "include_history": True,
        "enable_model_enhancement": False,
    }
    run_check(results, base_url, "diagnosis_analyze", "POST", "/diagnosis/analyze", token=token, payload=diagnosis_payload)

    sop_payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation",
        "maintenance_level": "level_2",
        "include_references": True,
        "enable_model_enhancement": False,
    }
    run_check(results, base_url, "sop_generate", "POST", "/sop/generate", token=token, payload=sop_payload)

    run_check(results, base_url, "maintenance_tasks", "GET", "/maintenance/tasks?page=1&page_size=5", token=token)
    run_check(results, base_url, "record_center_overview", "GET", "/record-center/overview", token=token)
    run_check(results, base_url, "model_gateway_status", "GET", "/model-gateway/status", token=token)

    failed = [item for item in results if not item.passed]
    report = {
        "status": "failed" if failed else "passed",
        "base_url": base_url,
        "writes_note": "retrieval_query and diagnosis_analyze create traceable smoke records with Task14A_Smoke marker; no data is deleted.",
        "results": [asdict(item) for item in results],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
