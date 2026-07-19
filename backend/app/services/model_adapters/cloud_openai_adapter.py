from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.model_gateway import ModelProviderStatus
from app.services.model_adapters.base import ModelAdapterRequest, ModelAdapterResponse


class CloudOpenAIAdapter:
    provider = "cloud_openai"
    _shared_clients: dict[tuple[str, int], httpx.Client] = {}
    _client_lock = threading.Lock()

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
            "temperature": adapter_request.temperature if adapter_request.temperature is not None else self.settings.CLOUD_LLM_TEMPERATURE,
            "max_tokens": adapter_request.max_tokens or self.settings.CLOUD_LLM_MAX_TOKENS,
        }
        if adapter_request.response_format:
            payload["response_format"] = adapter_request.response_format
        if adapter_request.reasoning_effort:
            payload["reasoning_effort"] = adapter_request.reasoning_effort
        timeout = adapter_request.timeout_seconds or self.settings.CLOUD_LLM_TIMEOUT_SECONDS
        try:
            response = self._shared_client(endpoint, timeout).post(
                endpoint,
                json=payload,
                headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.CLOUD_LLM_API_KEY}",
                },
            )
            response.raise_for_status()
            parsed = response.json()
            if not isinstance(parsed, dict):
                return self._call_failed(started_at, "Cloud model returned a non-object JSON response.")
            content = self._extract_content(parsed)
            response_meta = self._response_meta(parsed)
            if not content:
                return self._call_failed(
                    started_at,
                    "Cloud model returned empty content.",
                    error_code="empty_content",
                    provider_status="empty_content",
                    provider_request_id=str(
                        response.headers.get("x-request-id")
                        or response.headers.get("request-id")
                        or parsed.get("id")
                        or ""
                    ) or None,
                    raw_payload=response_meta,
                )
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
                    **response_meta,
                },
                provider_status="success",
                provider_request_id=str(
                    response.headers.get("x-request-id")
                    or response.headers.get("request-id")
                    or parsed.get("id")
                    or ""
                ) or None,
            )
        except httpx.HTTPStatusError as exc:
            return self._call_failed(
                started_at,
                self._sanitize_error(self._format_http_error(exc.response)),
                error_code=f"http_{exc.response.status_code}",
                provider_status="rejected",
                provider_request_id=exc.response.headers.get("x-request-id") or exc.response.headers.get("request-id"),
            )
        except httpx.TimeoutException:
            return self._call_failed(started_at, "Cloud model call timed out.", error_code="timeout", provider_status="timeout")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return self._call_failed(started_at, "Cloud model returned invalid JSON.", error_code="invalid_provider_json")
        except (httpx.NetworkError, httpx.HTTPError, OSError) as exc:
            return self._call_failed(
                started_at,
                self._sanitize_error(f"Cloud model call failed: {type(exc).__name__}"),
                error_code="network_error",
                provider_status="network_error",
            )

    @classmethod
    def _shared_client(cls, endpoint: str, timeout_seconds: float) -> httpx.Client:
        origin = str(httpx.URL(endpoint).copy_with(path="/", query=None, fragment=None))
        key = (origin, max(1, int(round(timeout_seconds))))
        with cls._client_lock:
            client = cls._shared_clients.get(key)
            if client is None or client.is_closed:
                client = httpx.Client(
                    timeout=httpx.Timeout(
                        connect=min(10.0, float(timeout_seconds)),
                        read=float(timeout_seconds),
                        write=min(15.0, float(timeout_seconds)),
                        pool=min(5.0, float(timeout_seconds)),
                    ),
                    limits=httpx.Limits(max_connections=12, max_keepalive_connections=8, keepalive_expiry=120),
                    headers={"Connection": "keep-alive"},
                )
                cls._shared_clients[key] = client
            return client

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
            provider_status="blocked",
            error_code="not_configured_or_disabled",
        )

    def _call_failed(
        self,
        started_at: float,
        message: str,
        *,
        error_code: str = "provider_call_failed",
        provider_status: str = "failed",
        provider_request_id: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> ModelAdapterResponse:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=self.settings.CLOUD_LLM_MODEL,
            content="",
            success=False,
            latency_ms=latency_ms,
            error_message=message,
            provider_status=provider_status,
            error_code=error_code,
            provider_request_id=provider_request_id,
            raw_payload=raw_payload,
        )

    @staticmethod
    def _response_meta(payload: dict) -> dict[str, Any]:
        """Return non-sensitive response shape diagnostics, never model reasoning/content."""
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return {
            "finish_reason": first.get("finish_reason"),
            "message_field_names": sorted(str(key) for key in message)[:20],
            "has_reasoning": isinstance(reasoning, str) and bool(reasoning),
            "reasoning_length": len(reasoning) if isinstance(reasoning, str) else 0,
            "usage": {
                key: usage.get(key)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if isinstance(usage.get(key), int)
            },
        }

    @staticmethod
    def _format_http_error(response: httpx.Response) -> str:
        message = response.reason_phrase or "HTTP error"
        try:
            body = response.text
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
        return f"Cloud model HTTP {response.status_code}: {message}"

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
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                return "\n".join(part.strip() for part in parts if part.strip()).strip()
        content = first.get("text")
        return content.strip() if isinstance(content, str) else ""
