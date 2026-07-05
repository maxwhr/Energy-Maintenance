from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExternalApiProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_api_providers"

    provider_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    base_url_env_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_key_env_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_env_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    capabilities_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_configured")
    status_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_external_api_providers_provider_type", "provider_type"),
        Index("ix_external_api_providers_enabled", "enabled"),
        Index("ix_external_api_providers_status", "status"),
    )


class ExternalApiRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_api_routes"

    route_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    agent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    fallback_provider_codes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    allow_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    blocked_when_unconfigured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    safety_policy_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_external_api_routes_agent_code", "agent_code"),
        Index("ix_external_api_routes_tool_name", "tool_name"),
        Index("ix_external_api_routes_capability", "capability"),
        Index("ix_external_api_routes_primary_provider", "primary_provider_code"),
    )


class ExternalApiCallLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "external_api_call_logs"

    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_tool_call_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_tool_calls.id"), nullable=True
    )
    request_summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_external_api_call_logs_provider_code", "provider_code"),
        Index("ix_external_api_call_logs_capability", "capability"),
        Index("ix_external_api_call_logs_status", "status"),
        Index("ix_external_api_call_logs_created_at", "created_at"),
    )


class ExternalApiHealthCheck(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "external_api_health_checks"

    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_external_api_health_checks_provider_code", "provider_code"),
        Index("ix_external_api_health_checks_status", "status"),
        Index("ix_external_api_health_checks_checked_at", "checked_at"),
    )
