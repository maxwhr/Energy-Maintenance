from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from app.models.external_api import ExternalApiProvider
from app.services.external_api_request_builder import ExternalApiRequestBuilder
from app.services.external_api_response_parser import ExternalApiResponseParser
from app.services.external_api_sanitizer import ExternalApiSanitizer


@dataclass(slots=True)
class ExternalApiAdapterResult:
    status: str
    success: bool
    message: str
    provider_code: str | None = None
    capability: str | None = None
    model_name: str | None = None
    trace_id: str | None = None
    would_call: bool = False
    external_api_called: bool = False
    blocked_reason: str | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_summary: dict[str, Any] = field(default_factory=dict)
    response_summary: dict[str, Any] = field(default_factory=dict)
    normalized_result: dict[str, Any] = field(default_factory=dict)


class ExternalApiAdapter:
    api_style = "openai_compatible"

    def __init__(self, provider: ExternalApiProvider, config: dict[str, Any]):
        self.provider = provider
        self.config = config

    def check_status(self, provider_config: dict[str, Any] | None = None) -> ExternalApiAdapterResult:
        config = provider_config or self.config
        if not self.provider.enabled:
            return ExternalApiAdapterResult(
                status="disabled",
                success=False,
                provider_code=self.provider.provider_code,
                model_name=config.get("model_name") or self.provider.default_model_name,
                message="Provider is disabled.",
                blocked_reason="provider_disabled",
            )
        missing = self.missing_config_keys(config)
        if missing:
            return ExternalApiAdapterResult(
                status="not_configured",
                success=False,
                provider_code=self.provider.provider_code,
                model_name=config.get("model_name") or self.provider.default_model_name,
                message=f"Provider configuration is incomplete: {', '.join(missing)}.",
                blocked_reason="provider_not_configured",
                response_summary={"missing_config": missing},
            )
        return ExternalApiAdapterResult(
            status="blocked",
            success=False,
            provider_code=self.provider.provider_code,
            model_name=config.get("model_name") or self.provider.default_model_name,
            message="Provider configuration is present, but real external calls are disabled.",
            would_call=True,
            blocked_reason="real_external_call_disabled",
        )

    def build_request(
        self,
        capability: str,
        payload: dict[str, Any],
        provider_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return ExternalApiRequestBuilder.build(
            provider_code=self.provider.provider_code,
            provider_type=self.provider.provider_type,
            capability=capability,
            payload=payload,
            config=provider_config or self.config,
            api_style=self.api_style,
        )

    def invoke(
        self,
        payload: dict[str, Any],
        *,
        capability: str,
        dry_run: bool = True,
        mock_run: bool = False,
    ) -> ExternalApiAdapterResult:
        request_summary = self.sanitize_request(self.build_request(capability, payload))
        status = self.check_status()
        if status.status in {"disabled", "not_configured"}:
            status.capability = capability
            status.request_summary = request_summary
            status.response_summary = self.sanitize_response(status.response_summary)
            return status
        parsed = self.parse_response(
            {
                "dry_run": dry_run,
                "mock_run": mock_run,
                "external_api_called": False,
                "normalized_result": {},
            },
            capability,
        )
        return ExternalApiAdapterResult(
            status="would_call" if dry_run else "blocked",
            success=False,
            provider_code=self.provider.provider_code,
            capability=capability,
            model_name=self.config.get("model_name") or self.provider.default_model_name,
            would_call=True,
            external_api_called=False,
            blocked_reason="real_external_call_disabled",
            message=(
                f"{self.provider.provider_code} request is fully constructed for {capability}, "
                "but no real external API call was made."
            ),
            request_summary=request_summary,
            response_summary={
                "dry_run": dry_run,
                "mock_run": mock_run,
                "provider_type": self.provider.provider_type,
                "api_style": self.api_style,
                "normalized_result": parsed.get("normalized_result", {}),
            },
            normalized_result=parsed.get("normalized_result", {}),
        )

    def parse_response(self, raw_response: Any, capability: str) -> dict[str, Any]:
        return ExternalApiResponseParser.parse(raw_response, capability)

    def normalize_result(self, parsed_response: dict[str, Any], capability: str) -> dict[str, Any]:
        return self.parse_response(parsed_response, capability).get("normalized_result", {})

    def sanitize_request(self, request: dict[str, Any]) -> dict[str, Any]:
        return ExternalApiSanitizer.sanitize(request)

    def sanitize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return ExternalApiSanitizer.sanitize(response)

    def invoke_text_chat(self, request_summary: dict[str, Any]) -> ExternalApiAdapterResult:
        return self.invoke(request_summary, capability="text_chat", dry_run=True)

    def invoke_vision_analysis(self, request_summary: dict[str, Any]) -> ExternalApiAdapterResult:
        capability = str(request_summary.get("capability") or "vision_chat")
        return self.invoke(request_summary, capability=capability, dry_run=True)

    def invoke_ocr(self, request_summary: dict[str, Any]) -> ExternalApiAdapterResult:
        return self.invoke(request_summary, capability="ocr", dry_run=True)

    def invoke_structured_extract(self, request_summary: dict[str, Any]) -> ExternalApiAdapterResult:
        return self.invoke(request_summary, capability="structured_extract", dry_run=True)

    def missing_config_keys(self, provider_config: dict[str, Any] | None = None) -> list[str]:
        config = provider_config or self.config
        missing: list[str] = []
        if self.provider.base_url_env_key and not config.get("base_url"):
            missing.append(self.provider.base_url_env_key)
        if self.provider.requires_api_key and self.provider.api_key_env_key and not config.get("api_key_configured"):
            missing.append(self.provider.api_key_env_key)
        if self.provider.model_env_key and not config.get("model_name"):
            missing.append(self.provider.model_env_key)
        return missing

    def _json_request(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        api_key: str,
        timeout_seconds: int,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", **(extra_headers or {})}
        if api_key:
            headers[auth_header] = f"{auth_scheme} {api_key}" if auth_scheme else api_key
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(self._sanitize_error(f"HTTP {exc.code}: {self._read_error_body(exc)}")) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(self._sanitize_error(f"network error: {getattr(exc, 'reason', exc)}")) from exc
        except TimeoutError as exc:
            raise RuntimeError("request timed out") from exc
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError("provider returned invalid JSON") from exc
        return parsed if isinstance(parsed, dict) else {"raw_response": parsed}

    def _sanitize_error(self, message: str) -> str:
        text = str(message)
        api_key = str(self.config.get("api_key") or "")
        if api_key:
            text = text.replace(api_key, "***redacted***")
        text = ExternalApiSanitizer.sanitize(text, max_text_length=500)
        return str(text)[:500]

    @staticmethod
    def _read_error_body(exc: urllib.error.HTTPError) -> str:
        try:
            return exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:  # noqa: BLE001
            return str(exc.reason or "HTTP error")

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        normalized = (base_url or "").rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return f"{normalized}/v1/chat/completions"

    @staticmethod
    def _extract_text_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        output = payload.get("output")
        if isinstance(output, dict):
            text = output.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        for key in ("result", "text", "content", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _json_or_text(value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"text": value}
        except json.JSONDecodeError:
            return {"text": value, "raw_text": value}
