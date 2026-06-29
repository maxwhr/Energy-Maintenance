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
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(http_request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
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
        raise AssertionError(f"login {account.username} did not return access_token")
    return token


def test_provider(
    base_url: str,
    token: str,
    provider: str,
    *,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    status, response = request_json(
        "POST",
        f"{base_url}/model-gateway/test",
        token=token,
        payload={
            "provider": provider,
            "task_type": "qa",
            "allow_fallback": allow_fallback,
            "prompt": "华为 SUN2000 逆变器绝缘阻抗低告警时，应如何组织初步排查？",
        },
    )
    return assert_success(f"test provider {provider}", status, response)


def main() -> int:
    base_url = os.getenv("MODEL_GATEWAY_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
    admin = Account(
        os.getenv("MODEL_GATEWAY_ADMIN_USERNAME", "admin"),
        os.getenv("MODEL_GATEWAY_ADMIN_PASSWORD", "admin123456"),
    )
    viewer = Account(
        os.getenv("MODEL_GATEWAY_VIEWER_USERNAME", "viewer_task10"),
        os.getenv("MODEL_GATEWAY_VIEWER_PASSWORD", "viewer123456"),
    )

    admin_token = login(base_url, admin)

    status_code, status_response = request_json("GET", f"{base_url}/model-gateway/status", token=admin_token)
    status_data = assert_success("admin status", status_code, status_response)
    providers = {item["provider"]: item for item in status_data.get("providers", [])}
    if providers.get("rule_based", {}).get("available") is not True:
        raise AssertionError("rule_based provider is not available")

    trace_ids: list[str] = []
    rule_result = test_provider(base_url, admin_token, "rule_based", allow_fallback=True)
    if not rule_result.get("success") or rule_result.get("provider") != "rule_based":
        raise AssertionError(f"rule_based test returned unexpected payload: {rule_result}")
    trace_ids.append(rule_result["trace_id"])

    chat_status, chat_response = request_json(
        "POST",
        f"{base_url}/model-gateway/chat",
        token=admin_token,
        payload={
            "provider": "rule_based",
            "task_type": "qa",
            "allow_fallback": True,
            "messages": [
                {"role": "system", "content": "你是光伏逆变器检修助手。"},
                {"role": "user", "content": "阳光电源 SG 系列逆变器过温如何排查？"},
            ],
        },
    )
    chat_data = assert_success("rule_based chat", chat_status, chat_response)
    if not chat_data.get("success"):
        raise AssertionError(f"rule_based chat returned unexpected payload: {chat_data}")
    trace_ids.append(chat_data["trace_id"])

    for provider in ("local_llama_cpp", "cloud_openai"):
        result = test_provider(base_url, admin_token, provider, allow_fallback=True)
        if result.get("requested_provider") != provider:
            raise AssertionError(f"{provider} did not preserve requested_provider")
        if not result.get("fallback_used"):
            raise AssertionError(f"{provider} did not use fallback while disabled/unconfigured")
        if result.get("provider") != "rule_based":
            raise AssertionError(f"{provider} fallback did not return rule_based result")
        trace_ids.append(result["trace_id"])

    logs_status, logs_response = request_json(
        "GET",
        f"{base_url}/model-gateway/logs?page=1&page_size=20",
        token=admin_token,
    )
    logs_data = assert_success("admin logs", logs_status, logs_response)
    items = logs_data.get("items") or []
    if not items:
        raise AssertionError("model-gateway logs returned no items")

    detail_status, detail_response = request_json(
        "GET",
        f"{base_url}/model-gateway/logs/{items[0]['id']}",
        token=admin_token,
    )
    detail_data = assert_success("admin log detail", detail_status, detail_response)

    api_key = os.getenv("CLOUD_LLM_API_KEY", "")
    if api_key and api_key in json.dumps(detail_data, ensure_ascii=False):
        raise AssertionError("CLOUD_LLM_API_KEY was exposed in model call log detail")

    try:
        viewer_token = login(base_url, viewer)
    except AssertionError as exc:
        print(f"[skipped] viewer checks: {exc}")
    else:
        viewer_status, viewer_response = request_json(
            "GET",
            f"{base_url}/model-gateway/status",
            token=viewer_token,
        )
        assert_success("viewer status", viewer_status, viewer_response)
        blocked_status, blocked_response = request_json(
            "POST",
            f"{base_url}/model-gateway/test",
            token=viewer_token,
            payload={
                "provider": "cloud_openai",
                "task_type": "qa",
                "allow_fallback": True,
                "prompt": "viewer should not be able to call cloud model.",
            },
        )
        if blocked_status != 403 and blocked_response.get("code") != 40302:
            raise AssertionError(f"viewer write was not blocked: {blocked_status}, {blocked_response}")
        print("[passed] viewer restricted write")

    print("[passed] trace_ids:", ", ".join(trace_ids))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
