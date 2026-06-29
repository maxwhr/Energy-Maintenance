"""initial_schema

Revision ID: 20260601_0001
Revises:
Create Date: 2026-06-01 00:01:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), server_default="viewer", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "devices",
        _uuid_pk(),
        sa.Column("device_name", sa.String(length=128), nullable=False),
        sa.Column("manufacturer", sa.String(length=32), nullable=False),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("station_name", sa.String(length=128), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="normal", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_manufacturer", "devices", ["manufacturer"])
    op.create_index("ix_devices_product_series", "devices", ["product_series"])
    op.create_index("ix_devices_device_type", "devices", ["device_type"])
    op.create_index("ix_devices_status", "devices", ["status"])

    op.create_table(
        "knowledge_documents",
        _uuid_pk(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=32), nullable=False),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("document_type", sa.String(length=64), server_default="manual", nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("file_ext", sa.String(length=16), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("parse_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_manufacturer", "knowledge_documents", ["manufacturer"])
    op.create_index("ix_knowledge_documents_product_series", "knowledge_documents", ["product_series"])
    op.create_index("ix_knowledge_documents_device_type", "knowledge_documents", ["device_type"])
    op.create_index("ix_knowledge_documents_document_type", "knowledge_documents", ["document_type"])
    op.create_index("ix_knowledge_documents_parse_status", "knowledge_documents", ["parse_status"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_documents_created_at", "knowledge_documents", ["created_at"])

    op.create_table(
        "knowledge_chunks",
        _uuid_pk(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manufacturer", sa.String(length=32), nullable=False),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_manufacturer", "knowledge_chunks", ["manufacturer"])
    op.create_index("ix_knowledge_chunks_product_series", "knowledge_chunks", ["product_series"])
    op.create_index("ix_knowledge_chunks_device_type", "knowledge_chunks", ["device_type"])
    op.create_index("ix_knowledge_chunks_document_type", "knowledge_chunks", ["document_type"])
    op.create_index("ix_knowledge_chunks_chunk_index", "knowledge_chunks", ["chunk_index"])
    op.create_index("ix_knowledge_chunks_status", "knowledge_chunks", ["status"])

    op.create_table(
        "qa_records",
        _uuid_pk(),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("retrieved_chunks", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("suggested_steps", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_qa_records_trace_id", "qa_records", ["trace_id"], unique=True)
    op.create_index("ix_qa_records_manufacturer", "qa_records", ["manufacturer"])
    op.create_index("ix_qa_records_product_series", "qa_records", ["product_series"])
    op.create_index("ix_qa_records_device_type", "qa_records", ["device_type"])
    op.create_index("ix_qa_records_document_type", "qa_records", ["document_type"])
    op.create_index("ix_qa_records_created_at", "qa_records", ["created_at"])

    op.create_table(
        "diagnosis_records",
        _uuid_pk(),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("device_name", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("fault_type", sa.String(length=64), nullable=True),
        sa.Column("alarm_code", sa.String(length=64), nullable=True),
        sa.Column("alarm_info", sa.Text(), nullable=True),
        sa.Column("fault_description", sa.Text(), nullable=False),
        sa.Column("device_status", sa.String(length=64), nullable=True),
        sa.Column("possible_causes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("inspection_steps", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("safety_notes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("recommended_actions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_diagnosis_records_trace_id", "diagnosis_records", ["trace_id"], unique=True)
    op.create_index("ix_diagnosis_records_manufacturer", "diagnosis_records", ["manufacturer"])
    op.create_index("ix_diagnosis_records_product_series", "diagnosis_records", ["product_series"])
    op.create_index("ix_diagnosis_records_device_type", "diagnosis_records", ["device_type"])
    op.create_index("ix_diagnosis_records_fault_type", "diagnosis_records", ["fault_type"])
    op.create_index("ix_diagnosis_records_alarm_code", "diagnosis_records", ["alarm_code"])
    op.create_index("ix_diagnosis_records_created_at", "diagnosis_records", ["created_at"])

    op.create_table(
        "maintenance_tasks",
        _uuid_pk(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_name", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("fault_type", sa.String(length=64), nullable=True),
        sa.Column("alarm_code", sa.String(length=64), nullable=True),
        sa.Column("fault_description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=32), server_default="medium", nullable=False),
        sa.Column("task_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("assignee", sa.String(length=128), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("source_trace_id", sa.String(length=64), nullable=True),
        sa.Column("suggested_steps", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_tasks_manufacturer", "maintenance_tasks", ["manufacturer"])
    op.create_index("ix_maintenance_tasks_product_series", "maintenance_tasks", ["product_series"])
    op.create_index("ix_maintenance_tasks_device_type", "maintenance_tasks", ["device_type"])
    op.create_index("ix_maintenance_tasks_fault_type", "maintenance_tasks", ["fault_type"])
    op.create_index("ix_maintenance_tasks_priority", "maintenance_tasks", ["priority"])
    op.create_index("ix_maintenance_tasks_task_status", "maintenance_tasks", ["task_status"])
    op.create_index("ix_maintenance_tasks_source_trace_id", "maintenance_tasks", ["source_trace_id"])
    op.create_index("ix_maintenance_tasks_created_at", "maintenance_tasks", ["created_at"])

    op.create_table(
        "operation_logs",
        _uuid_pk(),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_logs_module", "operation_logs", ["module"])
    op.create_index("ix_operation_logs_action", "operation_logs", ["action"])
    op.create_index("ix_operation_logs_trace_id", "operation_logs", ["trace_id"])
    op.create_index("ix_operation_logs_created_at", "operation_logs", ["created_at"])

    op.create_table(
        "model_call_logs",
        _uuid_pk(),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("module", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_call_logs_trace_id", "model_call_logs", ["trace_id"])
    op.create_index("ix_model_call_logs_module", "model_call_logs", ["module"])
    op.create_index("ix_model_call_logs_created_at", "model_call_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("model_call_logs")
    op.drop_table("operation_logs")
    op.drop_table("maintenance_tasks")
    op.drop_table("diagnosis_records")
    op.drop_table("qa_records")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("devices")
    op.drop_table("users")
