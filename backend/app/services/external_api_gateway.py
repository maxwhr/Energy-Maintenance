from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import User
from app.models.external_api import (
    ExternalApiCallLog,
    ExternalApiHealthCheck,
    ExternalApiProvider,
    ExternalApiRoute,
)
from app.repositories.external_api_repository import ExternalApiRepository
from app.schemas.external_api import (
    ExternalApiCheckResponse,
    ExternalApiDryRunRequest,
    ExternalApiGatewayResult,
    ExternalApiHealthCheckRead,
    ExternalApiMockRunRequest,
    ExternalApiProviderRead,
    ExternalApiProviderStatusRead,
    ExternalApiRealRunRequest,
    ExternalApiRouteRead,
    ExternalApiStatusResponse,
)
from app.services.external_api_adapters import (
    BlockedAdapter,
    ExternalApiAdapter,
    ExternalApiAdapterResult,
    MimoMultimodalAdapter,
    MockAdapter,
    OcrApiAdapter,
    OpenAICompatibleAdapter,
)
from app.services.external_api_sanitizer import ExternalApiSanitizer


class ExternalApiGatewayError(ValueError):
    pass


class ExternalApiGateway:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.repository = ExternalApiRepository(db)

    def list_providers(
        self,
        *,
        provider_type: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> list[ExternalApiProviderRead]:
        return [
            ExternalApiProviderRead.model_validate(item)
            for item in self.repository.list_providers(
                provider_type=provider_type,
                enabled=enabled,
                status=status,
            )
        ]

    def get_provider(self, provider_code: str) -> ExternalApiProviderRead | None:
        provider = self.repository.get_provider(provider_code)
        return ExternalApiProviderRead.model_validate(provider) if provider else None

    def list_routes(
        self,
        *,
        agent_code: str | None = None,
        tool_name: str | None = None,
        capability: str | None = None,
    ) -> list[ExternalApiRouteRead]:
        return [
            ExternalApiRouteRead.model_validate(item)
            for item in self.repository.list_routes(
                agent_code=agent_code,
                tool_name=tool_name,
                capability=capability,
            )
        ]

    def status(self) -> ExternalApiStatusResponse:
        providers = [self._provider_status(item) for item in self.repository.list_providers()]
        routes = [ExternalApiRouteRead.model_validate(item) for item in self.repository.list_routes()]
        return ExternalApiStatusResponse(
            providers=providers,
            routes=routes,
            real_external_calls_enabled=bool(self.settings.EXTERNAL_REAL_CALLS_ENABLED),
        )

    def check_provider(self, provider_code: str, current_user: User) -> ExternalApiCheckResponse:
        provider = self.repository.get_provider(provider_code)
        if not provider:
            raise ExternalApiGatewayError("External API provider not found")
        started = time.perf_counter()
        result = self._adapter_for(provider).check_status()
        latency_ms = int((time.perf_counter() - started) * 1000)
        now = self._now()
        provider.status = result.status
        provider.status_checked_at = now
        health = ExternalApiHealthCheck(
            provider_code=provider.provider_code,
            status=result.status,
            latency_ms=latency_ms,
            error_code=result.error_code,
            error_message=result.error_message or result.blocked_reason,
            checked_at=now,
            created_by=current_user.id,
        )
        try:
            self.repository.update_provider(provider)
            self.repository.create_health_check(health)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ExternalApiGatewayError(f"External API provider check could not be saved: {exc}") from exc

        gateway_result = self._to_gateway_result(
            provider=provider,
            route=None,
            capability="status_check",
            request_summary={"provider_code": provider.provider_code, "operation": "check_status"},
            adapter_result=result,
            latency_ms=latency_ms,
            trace_id=self._new_trace_id("eah"),
        )
        return ExternalApiCheckResponse(**gateway_result.model_dump(mode="json"), checked_at=now)

    def dry_run(self, payload: ExternalApiDryRunRequest, current_user: User) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="dry_run",
            capability=payload.capability,
            current_user=current_user,
            provider_code=payload.provider_code,
            route_code=payload.route_code,
            agent_code=payload.agent_code,
            tool_name=payload.tool_name,
            input_summary=payload.input_summary,
            agent_run_id=None,
            agent_tool_call_id=None,
        )
        self.db.commit()
        return result

    def mock_run(self, payload: ExternalApiMockRunRequest, current_user: User) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="mock_run",
            capability=payload.capability,
            current_user=current_user,
            provider_code=payload.provider_code,
            route_code=payload.route_code,
            agent_code=payload.agent_code,
            tool_name=payload.tool_name,
            input_summary=payload.input_summary,
            agent_run_id=None,
            agent_tool_call_id=None,
        )
        self.db.commit()
        return result

    def real_run(self, payload: ExternalApiRealRunRequest, current_user: User) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="real_run",
            capability=payload.capability,
            current_user=current_user,
            provider_code=payload.provider_code,
            route_code=payload.route_code,
            agent_code=payload.agent_code,
            tool_name=payload.tool_name,
            input_summary=payload.input_summary,
            agent_run_id=None,
            agent_tool_call_id=None,
        )
        self.db.commit()
        return result

    def dry_run_provider(
        self,
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        current_user: User,
    ) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="dry_run",
            capability=capability,
            current_user=current_user,
            provider_code=provider_code,
            route_code=None,
            agent_code=None,
            tool_name=None,
            input_summary=payload,
            agent_run_id=None,
            agent_tool_call_id=None,
        )
        self.db.commit()
        return result

    def mock_run_provider(
        self,
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        current_user: User,
    ) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="mock_run",
            capability=capability,
            current_user=current_user,
            provider_code=provider_code,
            route_code=None,
            agent_code=None,
            tool_name=None,
            input_summary=payload,
            agent_run_id=None,
            agent_tool_call_id=None,
        )
        self.db.commit()
        return result

    def real_run_provider(
        self,
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        current_user: User,
    ) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="real_run",
            capability=capability,
            current_user=current_user,
            provider_code=provider_code,
            route_code=None,
            agent_code=None,
            tool_name=None,
            input_summary=payload,
            agent_run_id=None,
            agent_tool_call_id=None,
        )
        self.db.commit()
        return result

    def dry_run_for_tool(
        self,
        *,
        tool_name: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        agent_code: str | None = None,
        agent_run_id: str | None = None,
        agent_tool_call_id: UUID | None = None,
    ) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="dry_run",
            capability=capability,
            current_user=current_user,
            provider_code=None,
            route_code=None,
            agent_code=agent_code,
            tool_name=tool_name,
            input_summary=input_summary,
            agent_run_id=agent_run_id,
            agent_tool_call_id=agent_tool_call_id,
        )
        self.db.commit()
        return result

    def mock_run_for_tool(
        self,
        *,
        tool_name: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        agent_code: str | None = None,
        agent_run_id: str | None = None,
        agent_tool_call_id: UUID | None = None,
    ) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="mock_run",
            capability=capability,
            current_user=current_user,
            provider_code=None,
            route_code=None,
            agent_code=agent_code,
            tool_name=tool_name,
            input_summary=input_summary,
            agent_run_id=agent_run_id,
            agent_tool_call_id=agent_tool_call_id,
        )
        self.db.commit()
        return result

    def real_run_for_tool(
        self,
        *,
        tool_name: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        agent_code: str | None = None,
        agent_run_id: str | None = None,
        agent_tool_call_id: UUID | None = None,
        provider_code: str | None = None,
    ) -> ExternalApiGatewayResult:
        result = self._run_internal(
            mode="real_run",
            capability=capability,
            current_user=current_user,
            provider_code=provider_code,
            route_code=None,
            agent_code=agent_code,
            tool_name=tool_name,
            input_summary=input_summary,
            agent_run_id=agent_run_id,
            agent_tool_call_id=agent_tool_call_id,
        )
        self.db.commit()
        return result

    def resolve_provider_for_tool(
        self,
        *,
        tool_name: str | None,
        capability: str,
        agent_code: str | None = None,
        provider_code: str | None = None,
        route_code: str | None = None,
    ) -> tuple[ExternalApiRoute | None, ExternalApiProvider]:
        route = self.repository.find_route(
            route_code=route_code,
            agent_code=agent_code,
            tool_name=tool_name,
            capability=capability,
        )
        candidate_codes: list[str] = []
        if provider_code:
            candidate_codes.append(provider_code)
        if route:
            candidate_codes.append(route.primary_provider_code)
            if route.allow_fallback:
                candidate_codes.extend(route.fallback_provider_codes_json or [])
        for candidate in candidate_codes:
            provider = self.repository.get_provider(candidate)
            if provider:
                return route, provider
        raise ExternalApiGatewayError("External API provider route could not be resolved")

    def get_provider_effective_config(self, provider: ExternalApiProvider) -> dict[str, Any]:
        return self._provider_config(provider)

    def check_provider_configuration(self, provider: ExternalApiProvider) -> dict[str, Any]:
        adapter = self._adapter_for(provider)
        missing = adapter.missing_config_keys()
        return {
            "configured": not missing,
            "missing_config": missing,
            "enabled": provider.enabled,
            "status": provider.status,
        }

    def list_logs(
        self,
        *,
        provider_code: str | None = None,
        capability: str | None = None,
        status: str | None = None,
        success: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        items, total = self.repository.list_call_logs(
            provider_code=provider_code,
            capability=capability,
            status=status,
            success=success,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._log_payload(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_log(self, trace_id: str) -> dict[str, Any] | None:
        item = self.repository.get_call_log_by_trace_id(trace_id)
        return self._log_payload(item) if item else None

    def list_health_checks(
        self,
        *,
        provider_code: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        items, total = self.repository.list_health_checks(
            provider_code=provider_code,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [ExternalApiHealthCheckRead.model_validate(item).model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def _run_internal(
        self,
        *,
        mode: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        provider_code: str | None,
        route_code: str | None,
        agent_code: str | None,
        tool_name: str | None,
        agent_run_id: str | None,
        agent_tool_call_id: UUID | None,
    ) -> ExternalApiGatewayResult:
        route, provider = self.resolve_provider_for_tool(
            route_code=route_code,
            agent_code=agent_code,
            tool_name=tool_name,
            capability=capability,
            provider_code=provider_code,
        )
        raw_payload = {
            "capability": capability,
            "provider_code": provider.provider_code,
            "route_code": route.route_code if route else None,
            "tool_name": tool_name,
            "agent_code": agent_code,
            "input_summary": input_summary,
        }
        safe_payload = self.sanitize_summary(raw_payload)
        trace_id = self._new_trace_id("eag" if mode == "dry_run" else "eam" if mode == "mock_run" else "ear")
        started = time.perf_counter()
        adapter_payload = input_summary if mode == "real_run" else safe_payload
        adapter_result = self._invoke_adapter(provider, capability, adapter_payload, mode=mode)
        if mode == "dry_run" and adapter_result.status == "disabled":
            adapter_result.status = "blocked"
            adapter_result.blocked_reason = adapter_result.blocked_reason or "provider_disabled"
        latency_ms = int((time.perf_counter() - started) * 1000)
        gateway_result = self._to_gateway_result(
            provider=provider,
            route=route,
            capability=capability,
            request_summary=adapter_result.request_summary or safe_payload,
            adapter_result=adapter_result,
            latency_ms=latency_ms,
            trace_id=trace_id,
        )
        self.write_call_log(
            provider=provider,
            capability=capability,
            gateway_result=gateway_result,
            adapter_result=adapter_result,
            current_user=current_user,
            agent_run_id=agent_run_id,
            agent_tool_call_id=agent_tool_call_id,
            latency_ms=latency_ms,
        )
        return gateway_result

    def _invoke_adapter(
        self,
        provider: ExternalApiProvider,
        capability: str,
        request_summary: dict[str, Any],
        *,
        mode: str,
    ) -> ExternalApiAdapterResult:
        adapter: ExternalApiAdapter
        if mode == "mock_run":
            adapter = MockAdapter(provider, self._provider_config(provider))
            return adapter.invoke(request_summary, capability=capability, dry_run=False, mock_run=True)
        adapter = self._adapter_for(provider, allow_real_api=mode == "real_run")
        return adapter.invoke(request_summary, capability=capability, dry_run=mode != "real_run", mock_run=False)

    def _adapter_for(self, provider: ExternalApiProvider, *, allow_real_api: bool = False) -> ExternalApiAdapter:
        config = self._provider_config(provider, allow_real_api=allow_real_api)
        if provider.provider_code == "mimo_2_5":
            return MimoMultimodalAdapter(provider, config)
        if provider.provider_type == "ocr_provider":
            return OcrApiAdapter(provider, config)
        if provider.provider_type == "vision_model":
            return MimoMultimodalAdapter(provider, config)
        if provider.provider_type in {"text_model", "local_model"}:
            return OpenAICompatibleAdapter(provider, config)
        return BlockedAdapter(provider, config)

    def _provider_status(self, provider: ExternalApiProvider) -> ExternalApiProviderStatusRead:
        config = self._provider_config(provider)
        configured = not self._adapter_for(provider).missing_config_keys()
        if provider.status == "available":
            message = "Provider is available only for local rule-based or explicitly configured routing."
        elif not provider.enabled:
            message = "Provider is disabled or reserved for future configuration."
        elif not configured:
            message = "Provider environment configuration is incomplete."
        else:
            message = "Provider is configured; real calls require real_run=true and an explicit allow-real command."
        return ExternalApiProviderStatusRead(
            provider_code=provider.provider_code,
            provider_name=provider.provider_name,
            provider_type=provider.provider_type,
            enabled=provider.enabled,
            configured=configured,
            requires_api_key=provider.requires_api_key,
            status=provider.status,
            status_checked_at=provider.status_checked_at,
            capabilities=list(provider.capabilities_json or []),
            base_url_configured=bool(config.get("base_url")),
            api_key_configured=bool(config.get("api_key_configured")),
            model_configured=bool(config.get("model_name")),
            model_name=config.get("model_name") or provider.default_model_name,
            timeout_seconds=provider.timeout_seconds,
            message=message,
        )

    def _provider_config(self, provider: ExternalApiProvider, *, allow_real_api: bool = False) -> dict[str, Any]:
        base_url = self._env_value(provider.base_url_env_key)
        api_key = self._env_value(provider.api_key_env_key)
        model_name = self._env_value(provider.model_env_key) or provider.default_model_name
        config = {
            "base_url": base_url,
            "base_url_masked": self._masked_url(base_url),
            "api_key": api_key if allow_real_api else "",
            "api_key_configured": bool(api_key),
            "api_key_masked": self._mask_secret(api_key),
            "model_name": model_name,
            "timeout_seconds": provider.timeout_seconds,
            "max_tokens": provider.max_tokens,
            "temperature": float(provider.temperature) if provider.temperature is not None else None,
            "real_external_calls_enabled": bool(allow_real_api),
        }
        if provider.provider_code == "mimo_2_5":
            config.update(
                {
                    "api_profile": self._env_value("MIMO_API_PROFILE") or "openai_compatible_vision",
                    "temperature": self._float_env("MIMO_TEMPERATURE", config.get("temperature") or 0.1),
                    "max_tokens": self._int_env("MIMO_MAX_TOKENS", config.get("max_tokens") or 2048),
                    "timeout_seconds": self._int_env("MIMO_TIMEOUT_SECONDS", config.get("timeout_seconds") or 60),
                }
            )
        if provider.provider_code == "custom_ocr_api":
            config.update(
                {
                    "api_profile": self._env_value("OCR_API_PROFILE") or "openai_compatible_vision",
                    "timeout_seconds": self._int_env("OCR_API_TIMEOUT_SECONDS", config.get("timeout_seconds") or 60),
                }
            )
        if provider.provider_code == "cloud_openai_vision":
            config.update(
                {
                    "api_profile": self._env_value("CLOUD_VISION_API_PROFILE") or "openai_compatible_vision",
                    "timeout_seconds": self._int_env("CLOUD_VISION_TIMEOUT_SECONDS", config.get("timeout_seconds") or 60),
                }
            )
        return config

    def _to_gateway_result(
        self,
        *,
        provider: ExternalApiProvider,
        route: ExternalApiRoute | None,
        capability: str,
        request_summary: dict[str, Any],
        adapter_result: ExternalApiAdapterResult,
        latency_ms: int,
        trace_id: str,
    ) -> ExternalApiGatewayResult:
        normalized = self.sanitize_summary(adapter_result.normalized_result or {})
        response_summary = self.sanitize_summary(
            {
                **adapter_result.response_summary,
                "provider_code": provider.provider_code,
                "provider_type": provider.provider_type,
                "route_code": route.route_code if route else None,
                "latency_ms": latency_ms,
                "external_api_called": adapter_result.external_api_called,
                "normalized_result": normalized,
            }
        )
        return ExternalApiGatewayResult(
            trace_id=trace_id,
            status=adapter_result.status,
            success=adapter_result.success,
            provider_code=provider.provider_code,
            capability=capability,
            route_code=route.route_code if route else None,
            model_name=adapter_result.model_name or provider.default_model_name,
            would_call=adapter_result.would_call,
            external_api_called=adapter_result.external_api_called,
            blocked_reason=adapter_result.blocked_reason,
            message=adapter_result.message,
            request_summary=self.sanitize_summary(request_summary),
            response_summary=response_summary,
            normalized_result=normalized,
            latency_ms=latency_ms,
        )

    def build_sanitized_log(self, gateway_result: ExternalApiGatewayResult) -> dict[str, Any]:
        return {
            "request_summary_json": self.sanitize_summary(gateway_result.request_summary),
            "response_summary_json": self.sanitize_summary(gateway_result.response_summary),
        }

    def write_call_log(
        self,
        *,
        provider: ExternalApiProvider,
        capability: str,
        gateway_result: ExternalApiGatewayResult,
        adapter_result: ExternalApiAdapterResult,
        current_user: User,
        agent_run_id: str | None,
        agent_tool_call_id: UUID | None,
        latency_ms: int,
    ) -> ExternalApiCallLog:
        log_payload = self.build_sanitized_log(gateway_result)
        log = ExternalApiCallLog(
            trace_id=gateway_result.trace_id,
            provider_code=provider.provider_code,
            capability=capability,
            agent_run_id=agent_run_id,
            agent_tool_call_id=agent_tool_call_id,
            request_summary_json=log_payload["request_summary_json"],
            response_summary_json=log_payload["response_summary_json"],
            status=gateway_result.status,
            success=gateway_result.success,
            latency_ms=latency_ms,
            error_code=adapter_result.error_code,
            error_message=adapter_result.error_message or adapter_result.blocked_reason,
            token_usage_json=None,
            created_by=current_user.id,
            created_at=self._now(),
        )
        try:
            return self.repository.create_call_log(log)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ExternalApiGatewayError(f"External API call log write failed: {exc}") from exc

    def _log_payload(self, item: ExternalApiCallLog) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "trace_id": item.trace_id,
            "provider_code": item.provider_code,
            "capability": item.capability,
            "agent_run_id": item.agent_run_id,
            "agent_tool_call_id": str(item.agent_tool_call_id) if item.agent_tool_call_id else None,
            "request_summary_json": self.sanitize_summary(item.request_summary_json or {}),
            "response_summary_json": self.sanitize_summary(item.response_summary_json or {}),
            "status": item.status,
            "success": item.success,
            "latency_ms": item.latency_ms,
            "error_code": item.error_code,
            "error_message": item.error_message,
            "token_usage_json": item.token_usage_json,
            "created_by": str(item.created_by) if item.created_by else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def sanitize_summary(self, value: Any) -> Any:
        return ExternalApiSanitizer.sanitize(value)

    def _env_value(self, key: str | None) -> str:
        if not key:
            return ""
        if hasattr(self.settings, key):
            value = getattr(self.settings, key)
            return str(value or "").strip()
        return os.getenv(key, "").strip()

    def _int_env(self, key: str, default: int) -> int:
        try:
            return int(self._env_value(key) or default)
        except ValueError:
            return default

    def _float_env(self, key: str, default: float) -> float:
        try:
            return float(self._env_value(key) or default)
        except ValueError:
            return default

    @staticmethod
    def _mask_secret(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:3]}***{value[-3:]}"

    @staticmethod
    def _masked_url(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 20:
            return value
        return f"{value[:12]}...{value[-6:]}"

    @staticmethod
    def _new_trace_id(prefix: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{prefix}_{timestamp}_{uuid4().hex[:10]}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise ExternalApiGatewayError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ExternalApiGatewayError("page_size must be between 1 and 100")
