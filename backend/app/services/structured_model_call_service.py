from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from copy import deepcopy
from typing import Callable, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.schemas.structured_model import (
    StructuredModelRequest,
    StructuredModelResult,
    StructuredOutputMode,
    StructuredParseStrategy,
)
from app.services.model_adapters.base import ModelAdapterRequest, ModelAdapterResponse
from app.services.model_adapters.cloud_openai_adapter import CloudOpenAIAdapter
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter


T = TypeVar("T", bound=BaseModel)
ModelCall = Callable[[StructuredModelRequest, StructuredOutputMode], str]


def extract_json_payload(text: str) -> tuple[dict, StructuredParseStrategy]:
    value = (text or "").lstrip("\ufeff").strip()
    if not value:
        raise ValueError("empty structured model response")
    try:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("structured response must be a JSON object")
        return payload, "DIRECT_JSON"
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", value, flags=re.I | re.S)
    if fence:
        payload = json.loads(fence.group(1))
        if not isinstance(payload, dict):
            raise ValueError("structured response must be a JSON object")
        return payload, "CODE_FENCE_JSON"

    decoder = json.JSONDecoder()
    for offset, char in enumerate(value):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(value[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload, "FIRST_JSON_OBJECT"
    raise ValueError("no complete JSON object found")


class StructuredModelCallService:
    """Provider-aware structured output with schema validation and sanitized diagnostics."""

    _capability_cache: dict[tuple[str, str, str], StructuredOutputMode] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        model_call: ModelCall | None = None,
        minimax_adapter: MiniMaxAnthropicAdapter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_call = model_call
        self.adapters = {
            "cloud_openai": CloudOpenAIAdapter(self.settings),
            "minimax_anthropic": minimax_adapter or MiniMaxAnthropicAdapter(self.settings),
        }

    def call(self, request: StructuredModelRequest, response_model: type[T]) -> StructuredModelResult:
        trace_id = str(request.trace_context.get("trace_id") or f"sm_{uuid4().hex}")
        started = time.perf_counter()
        modes = self._modes(request)
        errors: list[str] = []
        attempt_count = 0
        last_response: ModelAdapterResponse | None = None
        last_hash: str | None = None
        last_strategy: StructuredParseStrategy = "FAILED"
        last_length = 0
        last_type: str | None = None
        last_fields: list[str] = []
        last_shape: dict[str, object] = {}
        last_response_meta: dict[str, object] = {}

        for mode in modes:
            attempt_count += 1
            try:
                if self.model_call is not None:
                    raw_text = self.model_call(request, mode)
                    response = ModelAdapterResponse(
                        provider=request.provider,
                        model_name=request.model or self.settings.CLOUD_LLM_MODEL,
                        content=raw_text,
                        success=True,
                        provider_status="success",
                    )
                else:
                    adapter = self.adapters.get(request.provider)
                    if adapter is None:
                        raise ValueError("unsupported structured model provider")
                    response = adapter.chat(self._adapter_request(request, mode, trace_id))
                last_response = response
                last_response_meta = dict(response.raw_payload or {})
                if not response.success:
                    code = response.error_code or "provider_call_failed"
                    errors.append(f"{mode}:{code}")
                    if self._format_unsupported(response):
                        continue
                    if not request.allow_retry:
                        break
                    continue
                if isinstance(response.structured_payload, dict):
                    payload = response.structured_payload
                    canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    last_length = len(canonical_payload)
                    last_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
                    last_type = "dict"
                    last_fields = sorted(str(key) for key in payload)[:30]
                    last_shape = {"tool_input": True, "field_count": len(payload)}
                    last_strategy = "TOOL_INPUT"
                    validated = response_model.model_validate(payload)
                    normalized = validated.model_dump(mode="json")
                    return self._success_result(
                        request=request,
                        mode=mode,
                        response=response,
                        normalized=normalized,
                        errors=errors,
                        attempt_count=attempt_count,
                        started=started,
                        trace_id=trace_id,
                        raw_hash=last_hash,
                        raw_length=last_length,
                        raw_type=last_type,
                        raw_shape=last_shape,
                        parse_strategy=last_strategy,
                        response_meta=last_response_meta,
                    )
                raw_text = response.content or ""
                last_length = len(raw_text)
                stripped_raw = raw_text.lstrip("\ufeff").strip()
                last_shape = {
                    "starts_with": stripped_raw[:1],
                    "ends_with": stripped_raw[-1:] if stripped_raw else "",
                    "open_braces": stripped_raw.count("{"),
                    "close_braces": stripped_raw.count("}"),
                    "open_brackets": stripped_raw.count("["),
                    "close_brackets": stripped_raw.count("]"),
                    "has_code_fence": "```" in stripped_raw,
                }
                last_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                try:
                    inspected = json.loads(raw_text.lstrip("\ufeff").strip())
                    last_type = type(inspected).__name__
                    if isinstance(inspected, dict):
                        last_fields = sorted(str(key) for key in inspected)[:30]
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    last_type = "non_direct_json"
                payload, last_strategy = extract_json_payload(raw_text)
                last_type = "dict"
                last_fields = sorted(str(key) for key in payload)[:30]
                validated = response_model.model_validate(payload)
                normalized = validated.model_dump(mode="json")
                return self._success_result(
                    request=request,
                    mode=mode,
                    response=response,
                    normalized=normalized,
                    errors=errors,
                    attempt_count=attempt_count,
                    started=started,
                    trace_id=trace_id,
                    raw_hash=last_hash,
                    raw_length=last_length,
                    raw_type=last_type,
                    raw_shape=last_shape,
                    parse_strategy=last_strategy,
                    response_meta=last_response_meta,
                )
            except ValidationError as exc:
                last_strategy = last_strategy if last_strategy != "FAILED" else "DIRECT_JSON"
                errors.extend(self._validation_codes(exc))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                last_strategy = "FAILED"
                errors.append(f"{mode}:parse:{type(exc).__name__}")
            if not request.allow_retry:
                break

        response_mode = modes[min(max(attempt_count - 1, 0), len(modes) - 1)]
        return StructuredModelResult(
            success=False,
            parsed_payload=None,
            raw_text_hash=last_hash,
            raw_text_length=last_length,
            raw_top_level_type=last_type,
            raw_shape=last_shape,
            response_format_mode=response_mode,
            structured_mode=self._execution_mode(response_mode),
            provider=request.provider,
            model=request.model,
            protocol="anthropic" if request.provider == "minimax_anthropic" else "openai_compatible",
            parse_strategy=last_strategy,
            validation_errors=list(dict.fromkeys(errors))[:20],
            provider_status=(last_response.provider_status if last_response else None) or "failed",
            provider_error_code=last_response.error_code if last_response else None,
            fallback_reason="structured_output_exhausted",
            attempt_count=attempt_count,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            trace_id=trace_id,
            provider_request_id=(
                None if request.provider == "minimax_anthropic"
                else last_response.provider_request_id if last_response else None
            ),
            provider_request_id_hash=self._hash_id(last_response.provider_request_id if last_response else None),
            tool_name=request.tool_name,
            tool_use_id_hash=str(last_response_meta.get("tool_use_id_hash") or "") or None,
            tool_call_count=int(last_response_meta.get("tool_call_count") or 0),
            tool_input_valid=bool(last_response_meta.get("tool_input_valid")),
            unexpected_text_block=bool(last_response_meta.get("unexpected_text_block")),
            unexpected_thinking_block=bool(last_response_meta.get("unexpected_thinking_block")),
            stop_reason=str(last_response_meta.get("stop_reason") or "") or None,
            response_field_names=last_fields,
            provider_response_meta=last_response_meta,
        )

    def probe(self, *, timeout_seconds: float | None = None) -> StructuredModelResult:
        class ProbePayload(BaseModel):
            ok: bool
            label: str

        request = StructuredModelRequest(
            purpose="structured_output_capability_probe",
            messages=[
                {"role": "system", "content": "Return the requested JSON object only."},
                {"role": "user", "content": "Return {\"ok\":true,\"label\":\"probe\"}."},
            ],
            response_schema=ProbePayload.model_json_schema(),
            schema_name="structured_output_probe",
            max_tokens=96,
            timeout_seconds=timeout_seconds or self.settings.QUERY_UNDERSTANDING_TIMEOUT_SECONDS,
            allow_retry=True,
            model=self.settings.CLOUD_LLM_MODEL,
        )
        return self.call(request, ProbePayload)

    def _modes(self, request: StructuredModelRequest) -> list[StructuredOutputMode]:
        if request.provider == "minimax_anthropic":
            return ["MINIMAX_ANTHROPIC_TOOL"]
        preferred = str(request.trace_context.get("preferred_mode") or "").upper()
        if preferred == "JSON_SCHEMA":
            return ["JSON_SCHEMA", "JSON_OBJECT", "PROMPT_ONLY"]
        if preferred == "JSON_OBJECT":
            return ["JSON_OBJECT", "PROMPT_ONLY"]
        if preferred == "PROMPT_ONLY":
            return ["PROMPT_ONLY"]
        configured = self.settings.STRUCTURED_OUTPUT_MODE.strip().lower()
        key = (request.provider, request.model or self.settings.CLOUD_LLM_MODEL, "structured_output")
        cached = self._capability_cache.get(key)
        if configured == "json_schema":
            return ["JSON_SCHEMA", "JSON_OBJECT", "PROMPT_ONLY"]
        if configured == "json_object":
            return ["JSON_OBJECT", "PROMPT_ONLY"]
        if configured == "prompt_only":
            return ["PROMPT_ONLY"]
        if self.model_call is not None:
            return ["JSON_SCHEMA", "PROMPT_ONLY"]
        if cached:
            if cached == "JSON_OBJECT":
                return ["JSON_OBJECT", "PROMPT_ONLY"]
            if cached == "PROMPT_ONLY":
                return ["PROMPT_ONLY"]
            return ["JSON_SCHEMA", "JSON_OBJECT", "PROMPT_ONLY"]
        return ["JSON_SCHEMA", "JSON_OBJECT", "PROMPT_ONLY"]

    def _remember_mode(self, request: StructuredModelRequest, mode: StructuredOutputMode) -> None:
        if mode == "MINIMAX_ANTHROPIC_TOOL":
            return
        if not self.settings.STRUCTURED_OUTPUT_PROBE_ENABLED:
            return
        key = (request.provider, request.model or self.settings.CLOUD_LLM_MODEL, "structured_output")
        with self._cache_lock:
            self._capability_cache[key] = mode

    @staticmethod
    def _adapter_request(request: StructuredModelRequest, mode: StructuredOutputMode, trace_id: str) -> ModelAdapterRequest:
        response_format = None
        if mode == "JSON_SCHEMA":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": deepcopy(request.response_schema),
                },
            }
        elif mode == "JSON_OBJECT":
            response_format = {"type": "json_object"}
        required_tool_name = (request.tool_name or request.schema_name) if mode == "MINIMAX_ANTHROPIC_TOOL" else None
        return ModelAdapterRequest(
            prompt="",
            messages=request.messages,
            model=request.model,
            task_type=request.purpose,  # type: ignore[arg-type]
            trace_id=trace_id,
            max_tokens=request.max_tokens,
            timeout_seconds=request.timeout_seconds,
            temperature=request.temperature,
            response_format=response_format,
            reasoning_effort=request.reasoning_effort,
            system=next((message.content for message in request.messages if message.role == "system"), None),
            tools=([
                {
                    "name": required_tool_name,
                    "description": request.tool_description,
                    "input_schema": deepcopy(request.response_schema),
                }
            ] if required_tool_name else None),
            tool_choice=({"type": "tool", "name": required_tool_name} if required_tool_name else None),
            required_tool_name=required_tool_name,
            thinking=({"type": "disabled"} if required_tool_name else None),
            top_p=request.top_p,
            service_tier=request.service_tier,
            allow_retry=request.allow_retry,
        )

    def _success_result(
        self,
        *,
        request: StructuredModelRequest,
        mode: StructuredOutputMode,
        response: ModelAdapterResponse,
        normalized: dict,
        errors: list[str],
        attempt_count: int,
        started: float,
        trace_id: str,
        raw_hash: str | None,
        raw_length: int,
        raw_type: str | None,
        raw_shape: dict[str, object],
        parse_strategy: StructuredParseStrategy,
        response_meta: dict[str, object],
    ) -> StructuredModelResult:
        self._remember_mode(request, mode)
        minimax = request.provider == "minimax_anthropic"
        return StructuredModelResult(
            success=True,
            parsed_payload=normalized,
            raw_text_hash=raw_hash,
            raw_text_length=raw_length,
            raw_top_level_type=raw_type,
            raw_shape=raw_shape,
            response_format_mode=mode,
            structured_mode=self._execution_mode(mode),
            provider=request.provider,
            model=request.model,
            protocol="anthropic" if minimax else "openai_compatible",
            parse_strategy=parse_strategy,
            validation_errors=errors,
            provider_status=response.provider_status or "success",
            provider_error_code=response.error_code,
            fallback_reason=None if attempt_count == 1 else "structured_mode_degraded",
            attempt_count=attempt_count,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            trace_id=trace_id,
            provider_request_id=None if minimax else response.provider_request_id,
            provider_request_id_hash=self._hash_id(response.provider_request_id),
            response_field_names=sorted(normalized.keys()),
            provider_response_meta=response_meta,
            tool_name=request.tool_name,
            tool_use_id_hash=str(response_meta.get("tool_use_id_hash") or "") or None,
            tool_call_count=int(response_meta.get("tool_call_count") or 0),
            tool_input_valid=bool(response_meta.get("tool_input_valid")),
            unexpected_text_block=bool(response_meta.get("unexpected_text_block")),
            unexpected_thinking_block=bool(response_meta.get("unexpected_thinking_block")),
            stop_reason=str(response_meta.get("stop_reason") or "") or None,
        )

    @staticmethod
    def _execution_mode(mode: StructuredOutputMode) -> str:
        return {
            "MINIMAX_ANTHROPIC_TOOL": "MINIMAX_ANTHROPIC_TOOL",
            "JSON_SCHEMA": "OPENAI_JSON_SCHEMA",
            "JSON_OBJECT": "OPENAI_JSON_OBJECT",
            "PROMPT_ONLY": "PROMPT_JSON",
        }[mode]

    @staticmethod
    def _hash_id(value: str | None) -> str | None:
        return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None

    @staticmethod
    def _format_unsupported(response: ModelAdapterResponse) -> bool:
        return response.error_code in {"http_400", "http_404", "http_415", "http_422", "unsupported_response_format"}

    @staticmethod
    def _validation_codes(exc: ValidationError) -> list[str]:
        output = []
        for item in exc.errors(include_url=False):
            location = ".".join(str(part) for part in item.get("loc") or ()) or "root"
            output.append(f"schema:{location}:{item.get('type', 'invalid')}")
        return output[:20]
