from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.model_gateway import ModelProviderStatus
from app.services.model_adapters.base import ModelAdapterRequest, ModelAdapterResponse


class MiniMaxAnthropicAdapter:
    """MiniMax Anthropic-compatible tool caller with sanitized telemetry only."""

    provider = "minimax_anthropic"
    _loop: asyncio.AbstractEventLoop | None = None
    _loop_thread: threading.Thread | None = None
    _loop_lock = threading.Lock()
    _clients: dict[str, httpx.AsyncClient] = {}

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.model_name = settings.MINIMAX_MODEL or "MiniMax-M3"
        self._client_override = client

    def status(self) -> ModelProviderStatus:
        configured = bool(
            self.settings.MINIMAX_API_KEY
            and self.settings.MINIMAX_ANTHROPIC_BASE_URL
            and self.settings.MINIMAX_MODEL
            and self.settings.MINIMAX_PROTOCOL.strip().lower() == "anthropic"
        )
        enabled = bool(self.settings.MINIMAX_ENABLED)
        if not enabled:
            availability = "disabled"
            message = "MiniMax Anthropic provider is disabled."
        elif not configured:
            availability = "not_configured"
            message = "MiniMax provider configuration is incomplete."
        else:
            availability = "not_checked"
            message = "MiniMax provider is configured; availability requires an explicit probe."
        return ModelProviderStatus(
            provider=self.provider,
            enabled=enabled,
            configured=configured,
            available=False,
            availability_status=availability,
            model_name=self.settings.MINIMAX_MODEL or None,
            base_url=None,
            base_url_configured=bool(self.settings.MINIMAX_ANTHROPIC_BASE_URL),
            model_configured=bool(self.settings.MINIMAX_MODEL),
            api_type="anthropic",
            api_key_configured=bool(self.settings.MINIMAX_API_KEY),
            message=message,
        )

    def chat(self, request: ModelAdapterRequest) -> ModelAdapterResponse:
        loop = self._background_loop()
        future = asyncio.run_coroutine_threadsafe(self.achat(request), loop)
        try:
            timeout = float(request.timeout_seconds or self.settings.MINIMAX_QUERY_TIMEOUT_SECONDS)
            return future.result(timeout=timeout + 0.1)
        except FutureTimeoutError:
            future.cancel()
            return self._failure(request, "timeout", "TIMEOUT")

    async def achat(self, request: ModelAdapterRequest) -> ModelAdapterResponse:
        if not self.settings.MINIMAX_ENABLED:
            return self._failure(request, "disabled", "PROVIDER_UNAVAILABLE")
        if not self.settings.TASK25B_ALLOW_REAL_API:
            return self._failure(request, "real_api_not_allowed", "PROVIDER_UNAVAILABLE")
        if (request.service_tier or self.settings.MINIMAX_SERVICE_TIER).strip().lower() != "standard":
            return self._failure(request, "cost_tier_not_authorized", "PROVIDER_UNAVAILABLE")
        if not (
            self.settings.MINIMAX_API_KEY
            and self.settings.MINIMAX_ANTHROPIC_BASE_URL
            and (request.model or self.settings.MINIMAX_MODEL)
        ):
            return self._failure(request, "not_configured", "PROVIDER_UNAVAILABLE")
        if not request.required_tool_name or not request.tools:
            return self._failure(request, "invalid_request", "TOOL_REQUIRED")

        timeout_seconds = float(request.timeout_seconds or self.settings.MINIMAX_QUERY_TIMEOUT_SECONDS)
        payload = self._payload(request)
        started = time.perf_counter()
        response: httpx.Response | None = None
        last_code = "PROVIDER_UNAVAILABLE"
        attempts = (
            max(1, min(2, int(self.settings.MINIMAX_MAX_RETRIES) + 1))
            if request.allow_retry else 1
        )
        attempt_count = 0
        for attempt in range(attempts):
            attempt_count = attempt + 1
            remaining = timeout_seconds - (time.perf_counter() - started)
            if remaining <= 0:
                return self._failure(request, "timeout", "TIMEOUT", latency_ms=self._elapsed(started))
            try:
                client = self._client_override or await self._shared_client(timeout_seconds)
                response = await client.post(
                    self.messages_url(self.settings.MINIMAX_ANTHROPIC_BASE_URL),
                    headers={
                        "Authorization": f"Bearer {self.settings.MINIMAX_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=httpx.Timeout(
                        connect=min(2.0, remaining),
                        read=remaining,
                        write=min(2.0, remaining),
                        pool=min(1.0, remaining),
                    ),
                )
                if response.status_code < 400:
                    break
                last_code = f"HTTP_{response.status_code}"
                retryable_status = response.status_code in {502, 503}
                if not retryable_status or attempt + 1 >= attempts:
                    return self._failure(
                        request,
                        "http_error",
                        last_code,
                        latency_ms=self._elapsed(started),
                        provider_request_id=self._request_id(response, None),
                    )
            except httpx.TimeoutException:
                return self._failure(request, "timeout", "TIMEOUT", latency_ms=self._elapsed(started))
            except httpx.ConnectError:
                last_code = "PROVIDER_UNAVAILABLE"
                if attempt + 1 >= attempts:
                    return self._failure(request, "transport_error", last_code, latency_ms=self._elapsed(started))
            except httpx.HTTPError:
                return self._failure(
                    request, "transport_error", "PROVIDER_UNAVAILABLE", latency_ms=self._elapsed(started)
                )
            if attempt + 1 < attempts:
                await asyncio.sleep(0.1 * (attempt + 1))

        if response is None:
            return self._failure(request, "no_response", last_code, latency_ms=self._elapsed(started))
        if time.perf_counter() - started >= timeout_seconds:
            return self._failure(request, "timeout", "TIMEOUT", latency_ms=self._elapsed(started))
        try:
            body = response.json()
        except ValueError:
            return self._failure(request, "invalid_json", "INVALID_RESPONSE", latency_ms=self._elapsed(started))
        if not isinstance(body, dict):
            return self._failure(request, "invalid_shape", "INVALID_RESPONSE", latency_ms=self._elapsed(started))

        parsed = self.parse_tool_response(body, request.required_tool_name)
        request_id = self._request_id(response, body)
        diagnostics = {
            **parsed["diagnostics"],
            "protocol": "anthropic",
            "thinking_enabled": self._thinking_enabled(request.model or self.settings.MINIMAX_MODEL),
            "service_tier": request.service_tier or self.settings.MINIMAX_SERVICE_TIER,
            "provider_request_id_hash": self._hash(request_id),
            "latency_ms": self._elapsed(started),
            "attempt_count": attempt_count,
            "token_usage": self._usage(body),
        }
        if parsed["error_code"]:
            return ModelAdapterResponse(
                provider=self.provider,
                model_name=request.model or self.settings.MINIMAX_MODEL,
                content="",
                success=False,
                latency_ms=round(diagnostics["latency_ms"]),
                error_message="MiniMax structured tool response was rejected.",
                usage=self._usage(body),
                raw_payload=diagnostics,
                provider_status="invalid_structured_response",
                error_code=parsed["error_code"],
                provider_request_id=request_id,
                diagnostics=diagnostics,
            )
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=request.model or self.settings.MINIMAX_MODEL,
            content="",
            success=True,
            latency_ms=round(diagnostics["latency_ms"]),
            usage=self._usage(body),
            raw_payload=diagnostics,
            provider_status="success",
            error_code=None,
            provider_request_id=request_id,
            structured_payload=parsed["tool_input"],
            diagnostics=diagnostics,
        )

    def _payload(self, request: ModelAdapterRequest) -> dict[str, Any]:
        system_parts = [message.content for message in request.messages if message.role == "system"]
        messages = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.role in {"user", "assistant"}
        ]
        model = request.model or self.settings.MINIMAX_MODEL
        payload = {
            "model": model,
            "system": request.system or "\n".join(system_parts),
            "messages": messages,
            "max_tokens": int(request.max_tokens or self.settings.MINIMAX_QUERY_MAX_TOKENS),
            "temperature": self.settings.MINIMAX_TEMPERATURE if request.temperature is None else request.temperature,
            "top_p": self.settings.MINIMAX_TOP_P if request.top_p is None else request.top_p,
            "service_tier": request.service_tier or self.settings.MINIMAX_SERVICE_TIER,
            "tools": request.tools,
            "tool_choice": request.tool_choice or {"type": "tool", "name": request.required_tool_name},
            "stream": False,
        }
        if not self._thinking_enabled(model):
            payload["thinking"] = request.thinking or {"type": "disabled"}
        return payload

    @staticmethod
    def _thinking_enabled(model: str | None) -> bool:
        return str(model or "").lower().startswith("minimax-m2")

    @staticmethod
    def parse_tool_response(body: dict[str, Any], required_tool_name: str) -> dict[str, Any]:
        content = body.get("content")
        blocks = content if isinstance(content, list) else []
        target: list[dict[str, Any]] = []
        all_tools: list[dict[str, Any]] = []
        block_types: list[str] = []
        unexpected_text = False
        unexpected_thinking = False
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "unknown")
            block_types.append(block_type)
            if block_type == "tool_use":
                all_tools.append(block)
                if block.get("name") == required_tool_name:
                    target.append(block)
            elif block_type == "text" and str(block.get("text") or "").strip():
                unexpected_text = True
            elif block_type == "thinking":
                unexpected_thinking = True

        error_code = None
        tool_input = None
        tool_use_id_hash = None
        if not all_tools:
            error_code = "NO_TOOL_USE"
        elif len(target) != 1 or len(all_tools) != 1:
            error_code = "WRONG_TOOL" if not target else "INVALID_TOOL_INPUT"
        elif not isinstance(target[0].get("input"), dict):
            error_code = "INVALID_TOOL_INPUT"
        else:
            tool_input = target[0]["input"]
            tool_use_id_hash = MiniMaxAnthropicAdapter._hash(str(target[0].get("id") or ""))
        base_resp = body.get("base_resp") if isinstance(body.get("base_resp"), dict) else {}
        diagnostics = {
            "tool_name": required_tool_name,
            "tool_use_id_hash": tool_use_id_hash,
            "tool_call_count": len(all_tools),
            "tool_input_valid": error_code is None,
            "unexpected_text_block": unexpected_text,
            "unexpected_thinking_block": unexpected_thinking,
            "thinking_content_logged": False,
            "content_block_types": block_types[:10],
            "stop_reason": body.get("stop_reason"),
            "base_resp_status_code": base_resp.get("status_code"),
            "provider_status": "success" if error_code is None else "invalid_structured_response",
        }
        return {"tool_input": tool_input, "error_code": error_code, "diagnostics": diagnostics}

    @classmethod
    async def aclose_shared(cls) -> None:
        clients = list(cls._clients.values())
        cls._clients.clear()
        for client in clients:
            if not client.is_closed:
                await client.aclose()

    @classmethod
    def close_shared(cls) -> None:
        if cls._loop is None or not cls._loop.is_running():
            return
        future = asyncio.run_coroutine_threadsafe(cls.aclose_shared(), cls._loop)
        try:
            future.result(timeout=5)
        except (FutureTimeoutError, RuntimeError):
            future.cancel()

    @classmethod
    def _background_loop(cls) -> asyncio.AbstractEventLoop:
        with cls._loop_lock:
            if cls._loop is None or cls._loop.is_closed():
                loop = asyncio.new_event_loop()
                def run_loop() -> None:
                    asyncio.set_event_loop(loop)
                    loop.run_forever()
                thread = threading.Thread(
                    target=run_loop,
                    name="minimax-anthropic-http",
                    daemon=True,
                )
                cls._loop = loop
                cls._loop_thread = thread
                thread.start()
            return cls._loop

    @classmethod
    async def _shared_client(cls, timeout_seconds: float) -> httpx.AsyncClient:
        key = f"{timeout_seconds:.3f}"
        client = cls._clients.get(key)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=8,
                    max_keepalive_connections=4,
                    keepalive_expiry=120,
                ),
            )
            cls._clients[key] = client
        return client

    @staticmethod
    def messages_url(base_url: str) -> str:
        value = (base_url or "").strip().rstrip("/")
        if value.endswith("/v1/messages"):
            return value
        if value.endswith("/v1"):
            return f"{value}/messages"
        return f"{value}/v1/messages"

    @staticmethod
    def _usage(body: dict[str, Any]) -> dict[str, Any]:
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return {
            "prompt_tokens": input_tokens if isinstance(input_tokens, int) else None,
            "completion_tokens": output_tokens if isinstance(output_tokens, int) else None,
            "total_tokens": (
                input_tokens + output_tokens
                if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                else None
            ),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        }

    @staticmethod
    def _request_id(response: httpx.Response | None, body: dict[str, Any] | None) -> str | None:
        if response is not None:
            header = response.headers.get("x-request-id") or response.headers.get("request-id")
            if header:
                return header
        value = (body or {}).get("id")
        return str(value) if value else None

    def _failure(
        self,
        request: ModelAdapterRequest,
        status: str,
        code: str,
        *,
        latency_ms: float = 0.0,
        provider_request_id: str | None = None,
    ) -> ModelAdapterResponse:
        diagnostics = {
            "protocol": "anthropic",
            "tool_name": request.required_tool_name,
            "tool_call_count": 0,
            "tool_input_valid": False,
            "unexpected_text_block": False,
            "unexpected_thinking_block": False,
            "thinking_content_logged": False,
            "provider_request_id_hash": self._hash(provider_request_id),
            "latency_ms": latency_ms,
        }
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=request.model or self.settings.MINIMAX_MODEL,
            content="",
            success=False,
            latency_ms=round(latency_ms),
            error_message="MiniMax provider call failed.",
            raw_payload=diagnostics,
            provider_status=status,
            error_code=code,
            provider_request_id=provider_request_id,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _elapsed(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)

    @staticmethod
    def _hash(value: str | None) -> str | None:
        return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None
