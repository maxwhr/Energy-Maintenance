from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib import error, request

from app.core.config import Settings
from app.schemas.model_gateway import ModelProviderStatus
from app.services.model_adapters.base import ModelAdapterRequest, ModelAdapterResponse


class CloudOpenAIAdapter:
    provider = "cloud_openai"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.CLOUD_LLM_MODEL or "cloud-openai-compatible"

    def status(self) -> ModelProviderStatus:
        enabled = self.settings.CLOUD_LLM_ENABLED
        configured = bool(
            self.settings.CLOUD_LLM_BASE_URL
            and self.settings.CLOUD_LLM_API_KEY
            and self.settings.CLOUD_LLM_MODEL
        )
        if not enabled:
            availability_status = "disabled"
            message = "Cloud OpenAI-compatible provider is disabled."
        elif not configured:
            availability_status = "not_configured"
            message = "Cloud provider is enabled but missing base_url, api_key, or model."
        else:
            availability_status = "not_checked"
            message = "Cloud provider is configured; availability is verified by test/chat calls."
        return ModelProviderStatus(
            provider=self.provider,
            enabled=enabled,
            configured=configured,
            available=False,
            availability_status=availability_status,
            model_name=self.settings.CLOUD_LLM_MODEL or None,
            base_url=self._masked_url(self.settings.CLOUD_LLM_BASE_URL) or None,
            api_type=self.settings.CLOUD_LLM_API_TYPE,
            api_key_configured=bool(self.settings.CLOUD_LLM_API_KEY),
            message=message,
        )

    def chat(self, adapter_request: ModelAdapterRequest) -> ModelAdapterResponse:
        if not self.settings.CLOUD_LLM_ENABLED:
            return self._failed("Cloud model provider is disabled.")
        if not self.settings.CLOUD_LLM_BASE_URL:
            return self._failed("Cloud model base URL is not configured.")
        if not self.settings.CLOUD_LLM_API_KEY:
            return self._failed("Cloud model API key is not configured.")
        if not self.settings.CLOUD_LLM_MODEL:
            return self._failed("Cloud model name is not configured.")

        started_at = time.perf_counter()
        endpoint = self._chat_completions_url(self.settings.CLOUD_LLM_BASE_URL)
        payload = {
            "model": self.settings.CLOUD_LLM_MODEL,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in adapter_request.messages
            ],
            "temperature": self.settings.CLOUD_LLM_TEMPERATURE,
            "max_tokens": self.settings.CLOUD_LLM_MAX_TOKENS,
        }
        data = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.CLOUD_LLM_API_KEY}",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.settings.CLOUD_LLM_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                return self._call_failed(started_at, "Cloud model returned a non-object JSON response.")
            content = self._extract_content(parsed)
            if not content:
                return self._call_failed(started_at, "Cloud model returned empty content.")
            usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else None
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return ModelAdapterResponse(
                provider=self.provider,
                model_name=self.settings.CLOUD_LLM_MODEL,
                content=content,
                success=True,
                latency_ms=latency_ms,
                usage=usage,
                raw_payload={
                    "id": parsed.get("id"),
                    "object": parsed.get("object"),
                    "model": parsed.get("model"),
                    "usage": usage,
                },
            )
        except error.HTTPError as exc:
            return self._call_failed(started_at, self._sanitize_error(self._format_http_error(exc)))
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            return self._call_failed(started_at, self._sanitize_error(f"Cloud model network error: {reason}"))
        except TimeoutError:
            return self._call_failed(started_at, "Cloud model call timed out.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._call_failed(started_at, "Cloud model returned invalid JSON.")
        except OSError as exc:
            return self._call_failed(started_at, self._sanitize_error(f"Cloud model call failed: {exc}"))

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return f"{normalized}/v1/chat/completions"

    def _sanitize_error(self, message: str) -> str:
        sanitized = message
        if self.settings.CLOUD_LLM_API_KEY:
            sanitized = sanitized.replace(self.settings.CLOUD_LLM_API_KEY, "***")
        sanitized = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", sanitized)
        return sanitized[:500]

    @staticmethod
    def _masked_url(base_url: str) -> str:
        if not base_url:
            return ""
        stripped = base_url.strip()
        if "://" not in stripped:
            return stripped[:24] + ("..." if len(stripped) > 24 else "")
        scheme, rest = stripped.split("://", 1)
        host, _, path = rest.partition("/")
        if len(host) > 12:
            visible_host = f"{host[:6]}...{host[-4:]}"
        else:
            visible_host = host
        return f"{scheme}://{visible_host}" + (f"/{path[:24]}..." if len(path) > 24 else (f"/{path}" if path else ""))

    def _failed(self, message: str) -> ModelAdapterResponse:
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=self.model_name,
            content="",
            success=False,
            error_message=message,
        )

    def _call_failed(self, started_at: float, message: str) -> ModelAdapterResponse:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=self.settings.CLOUD_LLM_MODEL,
            content="",
            success=False,
            latency_ms=latency_ms,
            error_message=message,
        )

    @staticmethod
    def _format_http_error(exc: error.HTTPError) -> str:
        message = exc.reason or "HTTP error"
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(body) if body else None
            if isinstance(parsed, dict):
                detail = parsed.get("error") or parsed.get("message") or parsed.get("detail")
                if isinstance(detail, dict):
                    message = str(detail.get("message") or detail.get("type") or message)
                elif isinstance(detail, str):
                    message = detail
                elif isinstance(parsed.get("code"), (str, int)):
                    message = f"{parsed.get('code')}: {message}"
            elif body:
                message = body[:300]
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            pass
        return f"Cloud model HTTP {exc.code}: {message}"

    @staticmethod
    def _extract_content(payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
        content = first.get("text")
        return content.strip() if isinstance(content, str) else ""
