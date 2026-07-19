from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import ModelCallLog, User
from app.repositories.model_call_log_repository import ModelCallLogRepository
from app.schemas.model_gateway import (
    ModelCallLogDetail,
    ModelCallLogPage,
    ModelCallLogRead,
    ModelGatewayChatRequest,
    ModelGatewayResponse,
    ModelGatewayStatus,
    ModelGatewayTestRequest,
    ModelMessage,
    ModelProvider,
)
from app.services.model_adapters import CloudOpenAIAdapter, LocalLlamaCppAdapter, MiniMaxAnthropicAdapter, RuleBasedAdapter
from app.services.model_adapters.base import ModelAdapter, ModelAdapterRequest, ModelAdapterResponse


ALLOWED_PROVIDERS = {"rule_based", "local_llama_cpp", "cloud_openai", "minimax_anthropic"}


class ModelGatewayServiceError(ValueError):
    pass


class ModelGatewayService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.log_repository = ModelCallLogRepository(db)
        self.adapters: dict[str, ModelAdapter] = {
            "rule_based": RuleBasedAdapter(),
            "local_llama_cpp": LocalLlamaCppAdapter(self.settings),
            "cloud_openai": CloudOpenAIAdapter(self.settings),
            "minimax_anthropic": MiniMaxAnthropicAdapter(self.settings),
        }

    def status(self) -> ModelGatewayStatus:
        providers = [adapter.status() for adapter in self.adapters.values()]
        providers = [self._enrich_provider_status(provider) for provider in providers]
        return ModelGatewayStatus(
            default_provider=self._default_provider(),
            fallback_enabled=self.settings.MODEL_GATEWAY_ALLOW_FALLBACK,
            allow_fallback=self.settings.MODEL_GATEWAY_ALLOW_FALLBACK,
            logging_enabled=self.settings.MODEL_GATEWAY_ENABLE_LOGGING,
            timeout_seconds=self.settings.MODEL_GATEWAY_TIMEOUT_SECONDS,
            providers=providers,
        )

    def test(self, payload: ModelGatewayTestRequest, current_user: User) -> ModelGatewayResponse:
        return self._execute(payload, current_user=current_user)

    def chat(self, payload: ModelGatewayChatRequest, current_user: User) -> ModelGatewayResponse:
        return self._execute(payload, current_user=current_user)

    def list_logs(
        self,
        *,
        provider: str | None = None,
        model_name: str | None = None,
        call_type: str | None = None,
        success: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ModelCallLogPage:
        self._validate_page(page, page_size)
        items, total = self.log_repository.list(
            provider=provider,
            model_name=model_name,
            call_type=call_type,
            success=success,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return ModelCallLogPage(
            items=[ModelCallLogRead.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_log(self, log_id: UUID) -> ModelCallLogDetail | None:
        log = self.log_repository.get_by_id(log_id)
        if not log:
            return None
        return ModelCallLogDetail.model_validate(log)

    def _execute(
        self,
        payload: ModelGatewayTestRequest | ModelGatewayChatRequest,
        *,
        current_user: User,
    ) -> ModelGatewayResponse:
        trace_id = self._new_trace_id()
        requested_provider = payload.provider or self._default_provider()
        adapter_request = self._build_adapter_request(payload, trace_id)
        first_result = self._call_adapter(
            provider=requested_provider,
            adapter_request=adapter_request,
            requested_provider=requested_provider,
            current_user=current_user,
            fallback_used=False,
        )
        if first_result.success:
            return self._to_response(
                result=first_result,
                requested_provider=requested_provider,
                task_type=payload.task_type,
                trace_id=trace_id,
                fallback_used=False,
            )

        allow_fallback = payload.allow_fallback and self.settings.MODEL_GATEWAY_ALLOW_FALLBACK
        if allow_fallback and requested_provider != "rule_based":
            fallback_result = self._call_adapter(
                provider="rule_based",
                adapter_request=adapter_request,
                requested_provider=requested_provider,
                current_user=current_user,
                fallback_used=True,
                provider_error=first_result.error_message,
            )
            response = self._to_response(
                result=fallback_result,
                requested_provider=requested_provider,
                task_type=payload.task_type,
                trace_id=trace_id,
                fallback_used=True,
            )
            response.error_message = first_result.error_message
            return response

        return self._to_response(
            result=first_result,
            requested_provider=requested_provider,
            task_type=payload.task_type,
            trace_id=trace_id,
            fallback_used=False,
        )

    def _call_adapter(
        self,
        *,
        provider: ModelProvider,
        adapter_request: ModelAdapterRequest,
        requested_provider: ModelProvider,
        current_user: User,
        fallback_used: bool,
        provider_error: str | None = None,
    ) -> ModelAdapterResponse:
        adapter = self.adapters.get(provider)
        if not adapter:
            result = ModelAdapterResponse(
                provider=provider,
                model_name=provider,
                content="",
                success=False,
                error_message=f"Unsupported model provider: {provider}",
            )
        else:
            result = adapter.chat(adapter_request)
            if not result.content and result.success:
                result.success = False
                result.error_message = "Model provider returned empty content."

        self._save_log(
            result=result,
            adapter_request=adapter_request,
            requested_provider=requested_provider,
            current_user=current_user,
            fallback_used=fallback_used,
            provider_error=provider_error,
        )
        return result

    def _save_log(
        self,
        *,
        result: ModelAdapterResponse,
        adapter_request: ModelAdapterRequest,
        requested_provider: ModelProvider,
        current_user: User,
        fallback_used: bool,
        provider_error: str | None,
    ) -> None:
        if not self.settings.MODEL_GATEWAY_ENABLE_LOGGING:
            return
        minimax = result.provider == "minimax_anthropic"
        request_payload = {
            "requested_provider": requested_provider,
            "actual_provider": result.provider,
            "task_type": adapter_request.task_type,
            "fallback_used": fallback_used,
            "message_count": len(adapter_request.messages),
            "messages": (
                [
                    {
                        "role": message.role,
                        "content_length": len(message.content),
                        "content_hash": self._hash_text(message.content),
                    }
                    for message in adapter_request.messages
                ]
                if minimax else
                [{"role": message.role, "content": message.content} for message in adapter_request.messages]
            ),
            "provider_config": self._safe_provider_config(result.provider),
        }
        if provider_error:
            request_payload["provider_error"] = "upstream_provider_failed" if minimax else provider_error
        response_payload: dict[str, Any] = {
            "success": result.success,
            "fallback_used": fallback_used,
            "usage": result.usage,
            "raw_payload": result.raw_payload,
        }
        log = ModelCallLog(
            trace_id=adapter_request.trace_id,
            module="model_gateway",
            provider=result.provider,
            model_name=result.model_name,
            call_type=adapter_request.task_type,
            prompt=None if minimax else adapter_request.prompt,
            response=None if minimax else result.content or None,
            prompt_tokens=self._safe_int((result.usage or {}).get("prompt_tokens")),
            completion_tokens=self._safe_int((result.usage or {}).get("completion_tokens")),
            total_tokens=self._safe_int((result.usage or {}).get("total_tokens")),
            request_payload=request_payload,
            response_payload=response_payload,
            latency_ms=result.latency_ms,
            success=result.success,
            error_message=(result.error_code or result.provider_status) if minimax else result.error_message,
            created_by=current_user.id,
        )
        try:
            self.log_repository.create(log)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ModelGatewayServiceError(f"Model call log write failed: {exc}") from exc

    def _build_adapter_request(
        self,
        payload: ModelGatewayTestRequest | ModelGatewayChatRequest,
        trace_id: str,
    ) -> ModelAdapterRequest:
        if payload.messages:
            messages = payload.messages
            prompt = payload.prompt or "\n".join(
                f"{message.role}: {message.content}" for message in messages
            )
        else:
            prompt = payload.prompt or ""
            messages = [
                ModelMessage(
                    role="system",
                    content=(
                        "You are a maintenance assistant for Huawei and Sungrow PV inverters. "
                        "Keep responses source-aware and safety-conscious."
                    ),
                ),
                ModelMessage(role="user", content=prompt),
            ]
        return ModelAdapterRequest(
            prompt=prompt,
            messages=messages,
            task_type=payload.task_type,
            trace_id=trace_id,
            max_tokens=getattr(payload, "max_tokens_override", None),
            timeout_seconds=getattr(payload, "timeout_seconds_override", None),
        )

    def _to_response(
        self,
        *,
        result: ModelAdapterResponse,
        requested_provider: ModelProvider,
        task_type: str,
        trace_id: str,
        fallback_used: bool,
    ) -> ModelGatewayResponse:
        return ModelGatewayResponse(
            trace_id=trace_id,
            provider=result.provider,
            requested_provider=requested_provider,
            model_name=result.model_name,
            task_type=task_type,
            content=result.content,
            success=result.success,
            fallback_used=fallback_used,
            latency_ms=result.latency_ms,
            error_message=result.error_message,
            usage=result.usage,
        )

    def _default_provider(self) -> ModelProvider:
        value = self.settings.MODEL_GATEWAY_DEFAULT_PROVIDER
        if value not in ALLOWED_PROVIDERS:
            return "rule_based"
        return value  # type: ignore[return-value]

    def _safe_provider_config(self, provider: str) -> dict[str, Any]:
        if provider == "minimax_anthropic":
            return {
                "enabled": self.settings.MINIMAX_ENABLED,
                "model": self.settings.MINIMAX_MODEL,
                "protocol": self.settings.MINIMAX_PROTOCOL,
                "api_key_configured": bool(self.settings.MINIMAX_API_KEY),
                "thinking_enabled": self.settings.MINIMAX_THINKING_TYPE != "disabled",
                "service_tier": self.settings.MINIMAX_SERVICE_TIER,
                "tool_call_enabled": self.settings.MINIMAX_TOOL_CALL_ENABLED,
                "forced_tool_choice": self.settings.MINIMAX_FORCE_TOOL_CHOICE,
            }
        if provider == "cloud_openai":
            return {
                "enabled": self.settings.CLOUD_LLM_ENABLED,
                "base_url": self._masked_url(self.settings.CLOUD_LLM_BASE_URL),
                "model": self.settings.CLOUD_LLM_MODEL,
                "api_type": self.settings.CLOUD_LLM_API_TYPE,
                "api_key_configured": bool(self.settings.CLOUD_LLM_API_KEY),
                "timeout_seconds": self.settings.CLOUD_LLM_TIMEOUT_SECONDS,
                "max_tokens": self.settings.CLOUD_LLM_MAX_TOKENS,
            }
        if provider == "local_llama_cpp":
            return {
                "enabled": self.settings.LOCAL_LLM_ENABLED,
                "base_url": self.settings.LOCAL_LLM_BASE_URL,
                "model": self._path_label(self.settings.LOCAL_LLM_MODEL),
                "api_type": self.settings.LOCAL_LLM_API_TYPE,
                "base_url_configured": bool(self.settings.LOCAL_LLM_BASE_URL),
                "model_configured": bool(self.settings.LOCAL_LLM_MODEL),
                "timeout_seconds": self.settings.LOCAL_LLM_TIMEOUT_SECONDS,
                "max_tokens": self.settings.LOCAL_LLM_MAX_TOKENS,
                "health_path": self.settings.LOCAL_LLM_HEALTH_PATH,
                "native_completion_path": self.settings.LOCAL_LLM_NATIVE_COMPLETION_PATH,
                "openai_chat_path": self.settings.LOCAL_LLM_OPENAI_CHAT_PATH,
            }
        return {
            "enabled": True,
            "model": "rule_based_fallback_v1",
        }

    def _enrich_provider_status(self, status: Any) -> Any:
        if status.provider != "cloud_openai" or not status.enabled or not status.configured:
            return status
        latest = self.log_repository.get_latest_by_provider("cloud_openai")
        if not latest:
            return status
        if latest.success:
            status.available = True
            status.availability_status = "available"
            status.message = "Cloud OpenAI-compatible provider has a recent successful real call."
        else:
            status.available = False
            status.availability_status = "unavailable"
            status.message = "Cloud OpenAI-compatible provider is configured but the latest call failed."
        return status

    @staticmethod
    def _masked_url(base_url: str) -> str:
        if not base_url:
            return ""
        stripped = base_url.strip()
        if "://" not in stripped:
            return stripped[:24] + ("..." if len(stripped) > 24 else "")
        scheme, rest = stripped.split("://", 1)
        host, _, path = rest.partition("/")
        visible_host = f"{host[:6]}...{host[-4:]}" if len(host) > 12 else host
        if not path:
            return f"{scheme}://{visible_host}"
        visible_path = path if len(path) <= 24 else f"{path[:24]}..."
        return f"{scheme}://{visible_host}/{visible_path}"

    @staticmethod
    def _path_label(value: str) -> str:
        if not value:
            return ""
        normalized = value.replace("\\", "/").rstrip("/")
        return normalized.rsplit("/", 1)[-1]

    @staticmethod
    def _new_trace_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"mg_{timestamp}_{uuid4().hex[:10]}"

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise ModelGatewayServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ModelGatewayServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        return None

    @staticmethod
    def _hash_text(value: str) -> str:
        import hashlib

        return hashlib.sha256(value.encode("utf-8")).hexdigest()
