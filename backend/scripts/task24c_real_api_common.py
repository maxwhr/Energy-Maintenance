from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import error, parse, request

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402

API_BASE_URL = os.getenv("TASK24C_API_BASE_URL", "http://127.0.0.1:8010/api").rstrip("/")
ADMIN_USERNAME = os.getenv("TASK24C_ADMIN_USERNAME", os.getenv("FULL_SMOKE_ADMIN_USERNAME", "admin"))
ADMIN_PASSWORD = os.getenv("TASK24C_ADMIN_PASSWORD", os.getenv("FULL_SMOKE_ADMIN_PASSWORD", "admin123456"))
RUNTIME_DIR = ROOT_DIR / ".runtime" / "task24c"
MARKER = f"Task24C_{time.strftime('%Y%m%d%H%M%S')}"
SAMPLE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class Task24CError(AssertionError):
    pass


def api_base(base_url: str | None = None) -> str:
    return (base_url or API_BASE_URL).rstrip("/")


def request_json(
    method: str,
    path_or_url: str,
    *,
    base_url: str | None = None,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str = "application/json",
    timeout: int = 45,
) -> tuple[int, dict[str, Any]]:
    root = api_base(base_url)
    url = path_or_url if path_or_url.startswith("http") else f"{root}{path_or_url}"
    data = body
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif body is not None:
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {"code": exc.code, "message": exc.reason, "data": None}
        except json.JSONDecodeError:
            parsed = {"code": exc.code, "message": raw[:500], "data": None}
        return exc.code, parsed


def api_data(label: str, status: int, response: dict[str, Any]) -> Any:
    if status >= 400 or response.get("code") not in (0, 200):
        raise Task24CError(f"{label} failed: http={status}, code={response.get('code')}, message={response.get('message')}")
    return response.get("data")


def login(base_url: str | None = None, *, username: str | None = None, password: str | None = None) -> tuple[str, dict[str, Any]]:
    status, response = request_json(
        "POST",
        "/auth/login",
        base_url=base_url,
        payload={"username": username or ADMIN_USERNAME, "password": password or ADMIN_PASSWORD},
        timeout=30,
    )
    data = api_data("login", status, response)
    if not isinstance(data, dict) or not data.get("access_token"):
        raise Task24CError("login did not return access_token")
    return str(data["access_token"]), dict(data.get("user") or {})


def multipart_body(fields: list[tuple[str, str]], file_field: str, file_name: str, file_bytes: bytes, mime: str) -> tuple[bytes, str]:
    boundary = f"----EnergyMaintenanceTask24C{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields:
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
        .encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def upload_test_media(token: str, *, base_url: str | None = None, marker: str | None = None) -> str:
    marker = marker or MARKER
    body, content_type = multipart_body(
        [
            ("media_type", "fault_image"),
            ("description", f"{marker} PV inverter alarm screen real-call fixture"),
            ("manufacturer", "huawei"),
            ("product_series", "SUN2000"),
            ("device_type", "pv_inverter"),
            ("fault_type", "alarm_code_query"),
            ("alarm_code", "Task24C-ALM"),
        ],
        "file",
        f"{marker}_pv_inverter_alarm.png",
        SAMPLE_PNG,
        "image/png",
    )
    status, response = request_json("POST", "/media/upload", base_url=base_url, token=token, body=body, content_type=content_type)
    data = api_data("media upload", status, response)
    media_id = data.get("media_id") if isinstance(data, dict) else None
    if not media_id:
        raise Task24CError("media upload did not return media_id")
    return str(media_id)


def provider_config_summary() -> dict[str, Any]:
    settings = get_settings()
    return {
        "dashvector": {
            "enabled": settings.DASHVECTOR_ENABLED,
            "endpoint_configured": bool(settings.DASHVECTOR_ENDPOINT),
            "api_key_configured": bool(settings.DASHVECTOR_API_KEY),
            "collection_configured": bool(settings.DASHVECTOR_COLLECTION),
            "dimension": settings.DASHVECTOR_DIMENSION,
        },
        "embedding": {
            "enabled": settings.EMBEDDING_ENABLED,
            "base_url_configured": bool(settings.EMBEDDING_BASE_URL),
            "api_key_configured": bool(settings.EMBEDDING_API_KEY),
            "model_configured": bool(settings.EMBEDDING_MODEL),
            "dimension": settings.EMBEDDING_DIM,
            "provider": settings.EMBEDDING_PROVIDER,
        },
        "cloud_llm": {
            "enabled": settings.CLOUD_LLM_ENABLED,
            "base_url_configured": bool(settings.CLOUD_LLM_BASE_URL),
            "api_key_configured": bool(settings.CLOUD_LLM_API_KEY),
            "model_configured": bool(settings.CLOUD_LLM_MODEL),
            "api_type": settings.CLOUD_LLM_API_TYPE,
            "model_name": settings.CLOUD_LLM_MODEL or None,
        },
        "mimo": {
            "enabled": settings.MIMO_ENABLED,
            "base_url_configured": bool(settings.MIMO_BASE_URL),
            "api_key_configured": bool(settings.MIMO_API_KEY),
            "model_configured": bool(settings.MIMO_MODEL),
            "api_profile": settings.MIMO_API_PROFILE,
            "model_name": settings.MIMO_MODEL or None,
        },
        "ocr_api": {
            "enabled": settings.OCR_API_ENABLED,
            "base_url_configured": bool(settings.OCR_API_BASE_URL),
            "api_key_configured": bool(settings.OCR_API_KEY),
            "model_configured": bool(settings.OCR_API_MODEL),
            "model_name": settings.OCR_API_MODEL or None,
        },
        "cloud_vision": {
            "enabled": settings.CLOUD_VISION_ENABLED,
            "base_url_configured": bool(settings.CLOUD_VISION_BASE_URL),
            "api_key_configured": bool(settings.CLOUD_VISION_API_KEY),
            "model_configured": bool(settings.CLOUD_VISION_MODEL),
            "model_name": settings.CLOUD_VISION_MODEL or None,
        },
        "local_llm": {
            "enabled": settings.LOCAL_LLM_ENABLED,
            "base_url_configured": bool(settings.LOCAL_LLM_BASE_URL),
            "model_configured": bool(settings.LOCAL_LLM_MODEL),
            "model_name": settings.LOCAL_LLM_MODEL or None,
        },
        "tesseract": {
            "enabled": settings.OCR_ENABLED,
            "provider": settings.OCR_PROVIDER,
            "cmd_configured": bool(settings.OCR_TESSERACT_CMD),
        },
    }


def missing_config(provider: str) -> list[str]:
    settings = get_settings()
    missing: list[str] = []
    if provider == "dashvector":
        if not settings.DASHVECTOR_ENABLED:
            missing.append("DASHVECTOR_ENABLED")
        if not settings.DASHVECTOR_ENDPOINT:
            missing.append("DASHVECTOR_ENDPOINT")
        if not settings.DASHVECTOR_API_KEY:
            missing.append("DASHVECTOR_API_KEY")
        if not settings.DASHVECTOR_COLLECTION:
            missing.append("DASHVECTOR_COLLECTION")
        if settings.DASHVECTOR_DIMENSION <= 0:
            missing.append("DASHVECTOR_DIMENSION")
        if not settings.EMBEDDING_ENABLED:
            missing.append("EMBEDDING_ENABLED")
        if not settings.EMBEDDING_BASE_URL:
            missing.append("EMBEDDING_BASE_URL")
        if not settings.EMBEDDING_API_KEY:
            missing.append("EMBEDDING_API_KEY")
        if not settings.EMBEDDING_MODEL:
            missing.append("EMBEDDING_MODEL")
        if settings.EMBEDDING_DIM <= 0:
            missing.append("EMBEDDING_DIM")
        if settings.DASHVECTOR_DIMENSION and settings.EMBEDDING_DIM and settings.DASHVECTOR_DIMENSION != settings.EMBEDDING_DIM:
            missing.append("DASHVECTOR_DIMENSION must equal EMBEDDING_DIM")
    elif provider == "cloud_llm":
        if not settings.CLOUD_LLM_ENABLED:
            missing.append("CLOUD_LLM_ENABLED")
        if not settings.CLOUD_LLM_BASE_URL:
            missing.append("CLOUD_LLM_BASE_URL")
        if not settings.CLOUD_LLM_API_KEY:
            missing.append("CLOUD_LLM_API_KEY")
        if not settings.CLOUD_LLM_MODEL:
            missing.append("CLOUD_LLM_MODEL")
    elif provider == "mimo":
        if not settings.MIMO_ENABLED:
            missing.append("MIMO_ENABLED")
        if not settings.MIMO_BASE_URL:
            missing.append("MIMO_BASE_URL")
        if not settings.MIMO_API_KEY:
            missing.append("MIMO_API_KEY")
        if not settings.MIMO_MODEL:
            missing.append("MIMO_MODEL")
    elif provider == "ocr_api":
        if not settings.OCR_API_ENABLED:
            missing.append("OCR_API_ENABLED")
        if not settings.OCR_API_BASE_URL:
            missing.append("OCR_API_BASE_URL")
        if not settings.OCR_API_KEY:
            missing.append("OCR_API_KEY")
        if not settings.OCR_API_MODEL:
            missing.append("OCR_API_MODEL")
    return missing


def contains_sensitive_value(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    lowered = text.lower()
    forbidden_tokens = ["authorization", "bearer ", '"api_key":', "token=", "secret", "password", "data:image/"]
    if any(token in lowered for token in forbidden_tokens):
        return True
    if re.search(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*", text):
        return True
    if re.search(r"(?<!\w)/(?:home|Users|mnt|var|tmp|data|opt)/[^\s,;\"']+", text):
        return True
    if len(text.strip()) > 100 and all(ch.isalnum() or ch in "+/=\r\n" for ch in text.strip()):
        return True
    return False


def write_result(name: str, result: dict[str, Any]) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNTIME_DIR / name
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def query_string(params: dict[str, Any]) -> str:
    return parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
