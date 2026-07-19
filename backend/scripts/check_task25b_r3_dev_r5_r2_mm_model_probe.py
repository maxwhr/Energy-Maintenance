from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.schemas.model_gateway import ModelMessage  # noqa: E402
from app.schemas.structured_model import StructuredModelRequest  # noqa: E402
from app.services.structured_model_call_service import StructuredModelCallService  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm" / "minimax_model_probe.json"


class ProbePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    label: str


def _models_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    return f"{value}/models"


def _model_ids(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data") or payload.get("models") or []
    if not isinstance(rows, list):
        return []
    return sorted({str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id")})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "task": "Task 25B-R3-DEV-R5-R2-MM model probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "allow_real_api_cli": args.allow_real_api,
        "allow_real_api_env": settings.TASK25B_ALLOW_REAL_API,
        "enabled": settings.MINIMAX_ENABLED,
        "key_configured": bool(settings.MINIMAX_API_KEY),
        "protocol": settings.MINIMAX_PROTOCOL,
        "model": settings.MINIMAX_MODEL,
        "service_tier": settings.MINIMAX_SERVICE_TIER,
        "thinking_enabled": settings.MINIMAX_THINKING_TYPE != "disabled",
        "model_list_access": False,
        "m3_available": False,
        "model_ids": [],
        "anthropic_endpoint": False,
        "tool_use_received": False,
        "tool_input_valid": False,
        "thinking_content_logged": False,
        "secret_exposure": False,
        "passed": False,
        "failure_reason": None,
    }
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        result["failure_reason"] = "REAL_API_GUARD_CLOSED"
    elif not settings.MINIMAX_ENABLED or not settings.MINIMAX_API_KEY:
        result["failure_reason"] = "MINIMAX_NOT_CONFIGURED"
    elif settings.MINIMAX_SERVICE_TIER.strip().lower() != "standard":
        result["failure_reason"] = "PRIORITY_TIER_NOT_AUTHORIZED"
    else:
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=3, read=8, write=3, pool=2)) as client:
                response = client.get(
                    _models_url(settings.MINIMAX_OPENAI_BASE_URL),
                    headers={"Authorization": f"Bearer {settings.MINIMAX_API_KEY}"},
                )
                result["model_list_http_status"] = response.status_code
                if response.status_code < 400:
                    ids = _model_ids(response.json())
                    result["model_ids"] = ids
                    result["model_list_access"] = True
                    result["m3_available"] = settings.MINIMAX_MODEL in ids or "MiniMax-M3" in ids
        except (httpx.HTTPError, ValueError) as exc:
            result["model_list_error_type"] = exc.__class__.__name__
        request = StructuredModelRequest(
            purpose="structured_output_capability_probe",
            messages=[
                ModelMessage(role="system", content="必须调用 submit_minimax_probe；不输出普通文本或思维过程。"),
                ModelMessage(role="user", content="提交 ok=true 和 label=probe。"),
            ],
            response_schema=ProbePayload.model_json_schema(),
            schema_name="minimax_model_probe",
            tool_name="submit_minimax_probe",
            tool_description="提交极简模型可用性探针。",
            temperature=settings.MINIMAX_TEMPERATURE,
            top_p=settings.MINIMAX_TOP_P,
            service_tier="standard",
            max_tokens=min(256, settings.MINIMAX_QUERY_MAX_TOKENS),
            timeout_seconds=settings.MINIMAX_QUERY_TIMEOUT_SECONDS,
            allow_retry=False,
            provider="minimax_anthropic",
            model=settings.MINIMAX_MODEL,
        )
        structured = StructuredModelCallService(settings=settings).call(request, ProbePayload)
        result.update({
            "anthropic_endpoint": structured.provider_status not in {"disabled", "not_configured", "real_api_not_allowed"},
            "tool_use_received": structured.tool_call_count == 1,
            "tool_input_valid": structured.success and structured.tool_input_valid,
            "unexpected_text_block": structured.unexpected_text_block,
            "unexpected_thinking_block": structured.unexpected_thinking_block,
            "thinking_content_logged": bool(structured.provider_response_meta.get("thinking_content_logged")),
            "provider_status": structured.provider_status,
            "provider_error_code": structured.provider_error_code,
            "provider_request_id_hash": structured.provider_request_id_hash,
            "latency_ms": structured.latency_ms,
            "trace_id": structured.trace_id,
        })
        result["passed"] = all(result[key] for key in (
            "model_list_access", "m3_available", "anthropic_endpoint", "tool_use_received", "tool_input_valid",
        )) and not result["thinking_content_logged"]
        if not result["passed"] and result["failure_reason"] is None:
            result["failure_reason"] = "MODEL_PROBE_GATE_FAILED"
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "passed": result["passed"],
        "model_list_access": result["model_list_access"],
        "m3_available": result["m3_available"],
        "tool_use_received": result["tool_use_received"],
        "tool_input_valid": result["tool_input_valid"],
        "failure_reason": result["failure_reason"],
    }, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
