"""add_external_api_provider_gateway

Revision ID: 20260601_0005
Revises: 20260601_0004
Create Date: 2026-06-01 00:05:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0005"
down_revision: Union[str, None] = "20260601_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _jsonb(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "external_api_providers",
        _uuid_pk(),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("requires_api_key", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("base_url_env_key", sa.String(length=128), nullable=True),
        sa.Column("api_key_env_key", sa.String(length=128), nullable=True),
        sa.Column("model_env_key", sa.String(length=128), nullable=True),
        sa.Column("default_model_name", sa.String(length=128), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Numeric(5, 4), nullable=True),
        _jsonb("capabilities_json"),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'not_configured'"), nullable=False),
        sa.Column("status_checked_at", sa.DateTime(timezone=True), nullable=True),
        _jsonb("metadata_json"),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_code"),
    )
    op.create_index("ix_external_api_providers_provider_type", "external_api_providers", ["provider_type"])
    op.create_index("ix_external_api_providers_enabled", "external_api_providers", ["enabled"])
    op.create_index("ix_external_api_providers_status", "external_api_providers", ["status"])

    op.create_table(
        "external_api_routes",
        _uuid_pk(),
        sa.Column("route_code", sa.String(length=128), nullable=False),
        sa.Column("agent_code", sa.String(length=64), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=True),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("primary_provider_code", sa.String(length=64), nullable=False),
        _jsonb("fallback_provider_codes_json"),
        sa.Column("allow_fallback", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("blocked_when_unconfigured", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _jsonb("safety_policy_json"),
        _jsonb("metadata_json"),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_code"),
    )
    op.create_index("ix_external_api_routes_agent_code", "external_api_routes", ["agent_code"])
    op.create_index("ix_external_api_routes_tool_name", "external_api_routes", ["tool_name"])
    op.create_index("ix_external_api_routes_capability", "external_api_routes", ["capability"])
    op.create_index("ix_external_api_routes_primary_provider", "external_api_routes", ["primary_provider_code"])

    op.create_table(
        "external_api_call_logs",
        _uuid_pk(),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("agent_run_id", sa.String(length=128), nullable=True),
        sa.Column("agent_tool_call_id", postgresql.UUID(as_uuid=True), nullable=True),
        _jsonb("request_summary_json"),
        _jsonb("response_summary_json"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("success", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _jsonb("token_usage_json"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["agent_tool_call_id"], ["agent_tool_calls.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id"),
    )
    op.create_index("ix_external_api_call_logs_provider_code", "external_api_call_logs", ["provider_code"])
    op.create_index("ix_external_api_call_logs_capability", "external_api_call_logs", ["capability"])
    op.create_index("ix_external_api_call_logs_status", "external_api_call_logs", ["status"])
    op.create_index("ix_external_api_call_logs_created_at", "external_api_call_logs", ["created_at"])

    op.create_table(
        "external_api_health_checks",
        _uuid_pk(),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_api_health_checks_provider_code", "external_api_health_checks", ["provider_code"])
    op.create_index("ix_external_api_health_checks_status", "external_api_health_checks", ["status"])
    op.create_index("ix_external_api_health_checks_checked_at", "external_api_health_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_external_api_health_checks_checked_at", table_name="external_api_health_checks")
    op.drop_index("ix_external_api_health_checks_status", table_name="external_api_health_checks")
    op.drop_index("ix_external_api_health_checks_provider_code", table_name="external_api_health_checks")
    op.drop_table("external_api_health_checks")

    op.drop_index("ix_external_api_call_logs_created_at", table_name="external_api_call_logs")
    op.drop_index("ix_external_api_call_logs_status", table_name="external_api_call_logs")
    op.drop_index("ix_external_api_call_logs_capability", table_name="external_api_call_logs")
    op.drop_index("ix_external_api_call_logs_provider_code", table_name="external_api_call_logs")
    op.drop_table("external_api_call_logs")

    op.drop_index("ix_external_api_routes_primary_provider", table_name="external_api_routes")
    op.drop_index("ix_external_api_routes_capability", table_name="external_api_routes")
    op.drop_index("ix_external_api_routes_tool_name", table_name="external_api_routes")
    op.drop_index("ix_external_api_routes_agent_code", table_name="external_api_routes")
    op.drop_table("external_api_routes")

    op.drop_index("ix_external_api_providers_status", table_name="external_api_providers")
    op.drop_index("ix_external_api_providers_enabled", table_name="external_api_providers")
    op.drop_index("ix_external_api_providers_provider_type", table_name="external_api_providers")
    op.drop_table("external_api_providers")
