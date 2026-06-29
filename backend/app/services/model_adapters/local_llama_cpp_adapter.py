from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from app.core.config import Settings
from app.schemas.model_gateway import ModelProviderStatus
from app.services.model_adapters.base import ModelAdapterRequest, ModelAdapterResponse


SUPPORTED_API_TYPES = {"openai_compatible", "llama_cpp_native"}


@dataclass(slots=True)
class ProbeResult:
    available: bool
    latency_ms: int | None = None
    error_summary: str | None = None


class LocalLlamaCppAdapter:
    provider = "local_llama_cpp"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = self._model_label(settings.LOCAL_LLM_MODEL or "local-gguf-model")

    def status(self) -> ModelProviderStatus:
        enabled = self.settings.LOCAL_LLM_ENABLED
        base_url_configured = bool(self.settings.LOCAL_LLM_BASE_URL)
        model_configured = bool(self.settings.LOCAL_LLM_MODEL)
        api_type_valid = self.settings.LOCAL_LLM_API_TYPE in SUPPORTED_API_TYPES
        configured = base_url_configured and model_configured and api_type_valid

        probe = ProbeResult(False)
        availability_status = "disabled"
        message = "Local llama.cpp provider is disabled."
        if enabled and configured:
            probe = self._probe()
            availability_status = "available" if probe.available else "unavailable"
            message = (
                "Local llama.cpp-compatible service is reachable."
                if probe.available
                else "Local llama.cpp-compatible service is not reachable."
            )
        elif enabled:
            availability_status = "not_configured"
            if not api_type_valid:
                message = "Local llama.cpp API type must be openai_compatible or llama_cpp_native."
                probe.error_summary = "invalid_api_type"
            else:
                message = "Local llama.cpp provider is enabled but missing base_url or model."
                probe.error_summary = "missing_base_url_or_model"

        return ModelProviderStatus(
            provider=self.provider,
            enabled=enabled,
            configured=configured,
            available=probe.available,
            availability_status=availability_status,
            model_name=self.model_name if model_configured else None,
            base_url=self.settings.LOCAL_LLM_BASE_URL or None,
            base_url_configured=base_url_configured,
            model_configured=model_configured,
            api_type=self.settings.LOCAL_LLM_API_TYPE,
            health_path=self.settings.LOCAL_LLM_HEALTH_PATH,
            latency_ms=probe.latency_ms,
            error_summary=probe.error_summary,
            message=message,
        )

    def chat(self, adapter_request: ModelAdapterRequest) -> ModelAdapterResponse:
        validation_error = self._validation_error()
        if validation_error:
            return self._failed(validation_error)
        if self.settings.LOCAL_LLM_API_TYPE == "llama_cpp_native":
            return self._chat_native(adapter_request)
        return self._chat_openai_compatible(adapter_request)

    def _probe(self) -> ProbeResult:
        timeout = min(self.settings.LOCAL_LLM_TIMEOUT_SECONDS, 3)
        paths = [
            self.settings.LOCAL_LLM_HEALTH_PATH or "/health",
            "/",
            "/props",
        ]
        last_error = "unavailable"
        for path in dict.fromkeys(paths):
            started_at = time.perf_counter()
            endpoint = self._join_url(self.settings.LOCAL_LLM_BASE_URL, path)
            http_request = request.Request(endpoint, method="GET")
            try:
                with request.urlopen(http_request, timeout=timeout):
                    return ProbeResult(
                        True,
                        latency_ms=int((time.perf_counter() - started_at) * 1000),
                    )
            except error.HTTPError as exc:
                if exc.code == 404:
                    last_error = f"endpoint_mismatch: GET {path} returned HTTP 404"
                elif 200 <= exc.code < 500:
                    return ProbeResult(
                        True,
                        latency_ms=int((time.perf_counter() - started_at) * 1000),
                    )
                else:
                    last_error = f"unavailable: HTTP {exc.code}"
            except error.URLError as exc:
                reason = self._sanitize_error(str(getattr(exc, "reason", exc)))
                last_error = f"unavailable: {reason}"
            except TimeoutError:
                last_error = "unavailable: health check timed out"
            except OSError as exc:
                last_error = f"unavailable: {self._sanitize_error(str(exc))}"
        return ProbeResult(False, error_summary=last_error)

    def _chat_openai_compatible(self, adapter_request: ModelAdapterRequest) -> ModelAdapterResponse:
        started_at = time.perf_counter()
        endpoint = self._chat_url()
        payload = {
            "model": self.settings.LOCAL_LLM_MODEL,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in adapter_request.messages
            ],
            "temperature": self.settings.LOCAL_LLM_TEMPERATURE,
            "max_tokens": self.settings.LOCAL_LLM_MAX_TOKENS,
        }
        return self._post_json(endpoint, payload, started_at, response_kind="openai")

    def _chat_native(self, adapter_request: ModelAdapterRequest) -> ModelAdapterResponse:
        started_at = time.perf_counter()
        endpoint = self._join_url(
            self.settings.LOCAL_LLM_BASE_URL,
            self.settings.LOCAL_LLM_NATIVE_COMPLETION_PATH or "/completion",
        )
        payload = {
            "prompt": adapter_request.prompt,
            "temperature": self.settings.LOCAL_LLM_TEMPERATURE,
            "n_predict": self.settings.LOCAL_LLM_MAX_TOKENS,
        }
        return self._post_json(endpoint, payload, started_at, response_kind="native")

    def _post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        started_at: float,
        *,
        response_kind: str,
    ) -> ModelAdapterResponse:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.settings.LOCAL_LLM_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                return self._call_failed(started_at, "invalid_response: local model returned non-object JSON")
            content = self._extract_content(parsed, response_kind=response_kind)
            if not content:
                return self._call_failed(started_at, "empty_response: local model returned empty content")
            usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else None
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return ModelAdapterResponse(
                provider=self.provider,
                model_name=self.model_name,
                content=content,
                success=True,
                latency_ms=latency_ms,
                usage=usage,
                raw_payload={
                    "response_kind": response_kind,
                    "model": self._model_label(str(parsed.get("model") or self.model_name)),
                    "usage": usage,
                    "timings": parsed.get("timings") if isinstance(parsed.get("timings"), dict) else None,
                },
            )
        except error.HTTPError as exc:
            if exc.code == 404:
                return self._call_failed(started_at, "endpoint_mismatch: local llama.cpp endpoint returned HTTP 404")
            return self._call_failed(started_at, f"unavailable: local llama.cpp HTTP {exc.code}")
        except error.URLError as exc:
            reason = self._sanitize_error(str(getattr(exc, "reason", exc)))
            return self._call_failed(started_at, f"unavailable: {reason}")
        except TimeoutError:
            return self._call_failed(started_at, "unavailable: local llama.cpp call timed out")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._call_failed(started_at, "invalid_response: local llama.cpp returned invalid JSON")
        except OSError as exc:
            return self._call_failed(started_at, f"unavailable: {self._sanitize_error(str(exc))}")

    def _validation_error(self) -> str | None:
        if not self.settings.LOCAL_LLM_ENABLED:
            return "Local llama.cpp provider is disabled."
        if not self.settings.LOCAL_LLM_BASE_URL:
            return "Local llama.cpp base URL is not configured."
        if not self.settings.LOCAL_LLM_MODEL:
            return "Local llama.cpp model name is not configured."
        if self.settings.LOCAL_LLM_API_TYPE not in SUPPORTED_API_TYPES:
            return "Local llama.cpp API type must be openai_compatible or llama_cpp_native."
        return None

    def _failed(self, message: str) -> ModelAdapterResponse:
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=self.model_name,
            content="",
            success=False,
            error_message=self._sanitize_error(message),
        )

    def _call_failed(self, started_at: float, message: str) -> ModelAdapterResponse:
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=self.model_name,
            content="",
            success=False,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            error_message=self._sanitize_error(message),
        )

    def _chat_url(self) -> str:
        base_url = self.settings.LOCAL_LLM_BASE_URL.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return self._join_url(base_url, self.settings.LOCAL_LLM_OPENAI_CHAT_PATH or "/v1/chat/completions")

    @staticmethod
    def _join_url(base_url: str, path: str) -> str:
        normalized_base = base_url.rstrip("/")
        normalized_path = "/" + path.strip("/")
        if normalized_path == "/":
            return normalized_base
        if normalized_base.endswith(normalized_path):
            return normalized_base
        return f"{normalized_base}{normalized_path}"

    @staticmethod
    def _extract_content(payload: dict[str, Any], *, response_kind: str) -> str:
        if response_kind == "native":
            for key in ["content", "response", "completion"]:
                content = payload.get(key)
                if isinstance(content, str) and content.strip():
                    return content.strip()
            return ""
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

    @staticmethod
    def _model_label(value: str) -> str:
        stripped = value.strip()
        if not stripped:
            return "local-gguf-model"
        parts = re.split(r"[\\/]+", stripped)
        return parts[-1] if parts else stripped

    @staticmethod
    def _sanitize_error(message: str) -> str:
        sanitized = re.sub(r"[A-Za-z]:\\[^\\\s]+(?:\\[^\\\s]+)*", "<local-path>", message)
        sanitized = re.sub(r"/(?:[^/\s]+/)+[^/\s]+", "<local-path>", sanitized)
        return sanitized[:500]
