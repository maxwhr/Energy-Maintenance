"""enhance_schema_for_v2_requirements

Revision ID: 20260601_0002
Revises: 20260601_0001
Create Date: 2026-06-01 00:02:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0002"
down_revision: Union[str, None] = "20260601_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _json_list_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )


def _json_dict_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("devices", sa.Column("device_code", sa.String(length=64), nullable=True))
    op.add_column("devices", sa.Column("commissioning_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("last_fault_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("last_maintenance_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("fault_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("devices", sa.Column("maintenance_count", sa.Integer(), server_default="0", nullable=False))
    op.create_unique_constraint("uq_devices_device_code", "devices", ["device_code"])
    op.create_index("ix_devices_model", "devices", ["model"])

    op.add_column(
        "knowledge_documents",
        sa.Column("source_type", sa.String(length=64), server_default="user_upload", nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("review_status", sa.String(length=32), server_default="draft", nullable=False),
    )
    op.add_column("knowledge_documents", sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("knowledge_documents", sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("knowledge_documents", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_documents", sa.Column("review_comment", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_knowledge_documents_submitted_by_users",
        "knowledge_documents",
        "users",
        ["submitted_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_knowledge_documents_reviewed_by_users",
        "knowledge_documents",
        "users",
        ["reviewed_by"],
        ["id"],
    )
    op.create_index("ix_knowledge_documents_review_status", "knowledge_documents", ["review_status"])

    op.add_column("knowledge_chunks", sa.Column("content_hash", sa.String(length=128), nullable=True))

    op.add_column("qa_records", sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("qa_records", _json_list_column("safety_notes"))
    op.add_column("qa_records", _json_list_column("related_history"))
    op.add_column("qa_records", sa.Column("model_provider", sa.String(length=64), nullable=True))
    op.add_column("qa_records", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("qa_records", sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_qa_records_device_id_devices", "qa_records", "devices", ["device_id"], ["id"])
    op.create_foreign_key("fk_qa_records_created_by_users", "qa_records", "users", ["created_by"], ["id"])
    op.create_index("ix_qa_records_device_id", "qa_records", ["device_id"])
    op.create_index("ix_qa_records_model_provider", "qa_records", ["model_provider"])

    op.add_column("diagnosis_records", sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("diagnosis_records", _json_list_column("related_history"))
    op.add_column("diagnosis_records", _json_list_column("media_ids"))
    op.add_column("diagnosis_records", sa.Column("model_provider", sa.String(length=64), nullable=True))
    op.add_column("diagnosis_records", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("diagnosis_records", sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_diagnosis_records_device_id_devices",
        "diagnosis_records",
        "devices",
        ["device_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_diagnosis_records_created_by_users",
        "diagnosis_records",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index("ix_diagnosis_records_device_id", "diagnosis_records", ["device_id"])
    op.create_index("ix_diagnosis_records_model_provider", "diagnosis_records", ["model_provider"])

    op.add_column(
        "maintenance_tasks",
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
    )
    op.add_column("maintenance_tasks", sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("maintenance_tasks", sa.Column("sop_template_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("maintenance_tasks", sa.Column("sop_execution_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("maintenance_tasks", sa.Column("root_cause", sa.Text(), nullable=True))
    op.add_column("maintenance_tasks", sa.Column("repair_action", sa.Text(), nullable=True))
    op.add_column("maintenance_tasks", _json_list_column("replaced_parts"))
    op.add_column("maintenance_tasks", sa.Column("verification_result", sa.Text(), nullable=True))
    op.add_column(
        "maintenance_tasks",
        sa.Column("is_recurrent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("maintenance_tasks", sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("maintenance_tasks", sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_maintenance_tasks_device_id_devices", "maintenance_tasks", "devices", ["device_id"], ["id"])
    op.create_foreign_key("fk_maintenance_tasks_assignee_id_users", "maintenance_tasks", "users", ["assignee_id"], ["id"])
    op.create_foreign_key("fk_maintenance_tasks_completed_by_users", "maintenance_tasks", "users", ["completed_by"], ["id"])
    op.create_foreign_key("fk_maintenance_tasks_created_by_users", "maintenance_tasks", "users", ["created_by"], ["id"])
    op.create_index("ix_maintenance_tasks_device_id", "maintenance_tasks", ["device_id"])
    op.create_index("ix_maintenance_tasks_status", "maintenance_tasks", ["status"])

    op.add_column(
        "model_call_logs",
        sa.Column("call_type", sa.String(length=32), server_default="other", nullable=False),
    )
    op.add_column("model_call_logs", sa.Column("prompt", sa.Text(), nullable=True))
    op.add_column("model_call_logs", sa.Column("response", sa.Text(), nullable=True))
    op.add_column("model_call_logs", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column(
        "model_call_logs",
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("model_call_logs", sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_model_call_logs_created_by_users",
        "model_call_logs",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index("ix_model_call_logs_provider", "model_call_logs", ["provider"])
    op.create_index("ix_model_call_logs_model_name", "model_call_logs", ["model_name"])
    op.create_index("ix_model_call_logs_call_type", "model_call_logs", ["call_type"])
    op.create_index("ix_model_call_logs_success", "model_call_logs", ["success"])

    op.create_table(
        "sop_templates",
        _uuid_pk(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("fault_type", sa.String(length=64), nullable=True),
        sa.Column("maintenance_level", sa.String(length=32), server_default="level_1", nullable=False),
        _json_list_column("steps"),
        _json_list_column("safety_requirements"),
        _json_list_column("tools_required"),
        _json_list_column("materials_required"),
        sa.Column("compliance_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sop_templates_manufacturer", "sop_templates", ["manufacturer"])
    op.create_index("ix_sop_templates_product_series", "sop_templates", ["product_series"])
    op.create_index("ix_sop_templates_device_type", "sop_templates", ["device_type"])
    op.create_index("ix_sop_templates_fault_type", "sop_templates", ["fault_type"])
    op.create_index("ix_sop_templates_status", "sop_templates", ["status"])

    op.create_table(
        "sop_execution_records",
        _uuid_pk(),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("executor_id", postgresql.UUID(as_uuid=True), nullable=True),
        _json_list_column("step_results"),
        sa.Column("abnormal_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="not_started", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["executor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["sop_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sop_execution_records_task_id", "sop_execution_records", ["task_id"])
    op.create_index("ix_sop_execution_records_template_id", "sop_execution_records", ["template_id"])
    op.create_index("ix_sop_execution_records_status", "sop_execution_records", ["status"])
    op.create_index("ix_sop_execution_records_executor_id", "sop_execution_records", ["executor_id"])

    op.create_foreign_key(
        "fk_maintenance_tasks_sop_template_id_sop_templates",
        "maintenance_tasks",
        "sop_templates",
        ["sop_template_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_maintenance_tasks_sop_execution_id",
        "maintenance_tasks",
        "sop_execution_records",
        ["sop_execution_id"],
        ["id"],
    )

    op.create_table(
        "uploaded_media",
        _uuid_pk(),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_ext", sa.String(length=16), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("media_type", sa.String(length=32), server_default="other", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("diagnosis_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("qa_trace_id", sa.String(length=64), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="uploaded", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["diagnosis_record_id"], ["diagnosis_records.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_media_device_id", "uploaded_media", ["device_id"])
    op.create_index("ix_uploaded_media_task_id", "uploaded_media", ["task_id"])
    op.create_index("ix_uploaded_media_diagnosis_record_id", "uploaded_media", ["diagnosis_record_id"])
    op.create_index("ix_uploaded_media_media_type", "uploaded_media", ["media_type"])
    op.create_index("ix_uploaded_media_status", "uploaded_media", ["status"])
    op.create_index("ix_uploaded_media_qa_trace_id", "uploaded_media", ["qa_trace_id"])

    op.create_table(
        "device_maintenance_records",
        _uuid_pk(),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("diagnosis_trace_id", sa.String(length=64), nullable=True),
        sa.Column("qa_trace_id", sa.String(length=64), nullable=True),
        sa.Column("fault_type", sa.String(length=64), nullable=True),
        sa.Column("alarm_code", sa.String(length=64), nullable=True),
        sa.Column("fault_description", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("repair_action", sa.Text(), nullable=True),
        sa.Column("replaced_parts", sa.Text(), nullable=True),
        sa.Column("verification_result", sa.Text(), nullable=True),
        sa.Column("is_recurrent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("recurrent_reference_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _json_list_column("attachments"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["recurrent_reference_record_id"], ["device_maintenance_records.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_maintenance_records_device_id", "device_maintenance_records", ["device_id"])
    op.create_index("ix_device_maintenance_records_task_id", "device_maintenance_records", ["task_id"])
    op.create_index("ix_device_maintenance_records_fault_type", "device_maintenance_records", ["fault_type"])
    op.create_index("ix_device_maintenance_records_alarm_code", "device_maintenance_records", ["alarm_code"])
    op.create_index("ix_device_maintenance_records_completed_at", "device_maintenance_records", ["completed_at"])
    op.create_index("ix_device_maintenance_records_diagnosis_trace_id", "device_maintenance_records", ["diagnosis_trace_id"])
    op.create_index("ix_device_maintenance_records_qa_trace_id", "device_maintenance_records", ["qa_trace_id"])

    op.create_table(
        "knowledge_contributions",
        _uuid_pk(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contribution_type", sa.String(length=64), server_default="experience_summary", nullable=False),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("source_trace_id", sa.String(length=64), nullable=True),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("approved_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["approved_document_id"], ["knowledge_documents.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_contributions_review_status", "knowledge_contributions", ["review_status"])
    op.create_index("ix_knowledge_contributions_submitted_by", "knowledge_contributions", ["submitted_by"])
    op.create_index("ix_knowledge_contributions_source_trace_id", "knowledge_contributions", ["source_trace_id"])
    op.create_index("ix_knowledge_contributions_device_id", "knowledge_contributions", ["device_id"])

    op.create_table(
        "knowledge_review_records",
        _uuid_pk(),
        sa.Column("contribution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_action", sa.String(length=32), nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("before_status", sa.String(length=32), nullable=True),
        sa.Column("after_status", sa.String(length=32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["contribution_id"], ["knowledge_contributions.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_review_records_contribution_id", "knowledge_review_records", ["contribution_id"])
    op.create_index("ix_knowledge_review_records_document_id", "knowledge_review_records", ["document_id"])
    op.create_index("ix_knowledge_review_records_reviewer_id", "knowledge_review_records", ["reviewer_id"])
    op.create_index("ix_knowledge_review_records_review_action", "knowledge_review_records", ["review_action"])

    op.create_table(
        "model_output_corrections",
        _uuid_pk(),
        sa.Column("source_type", sa.String(length=32), server_default="qa", nullable=False),
        sa.Column("source_trace_id", sa.String(length=64), nullable=False),
        _json_dict_column("original_output"),
        _json_dict_column("corrected_output"),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_status", sa.String(length=32), server_default="pending_review", nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_contribution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["converted_contribution_id"], ["knowledge_contributions.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_output_corrections_source_trace_id", "model_output_corrections", ["source_trace_id"])
    op.create_index("ix_model_output_corrections_review_status", "model_output_corrections", ["review_status"])
    op.create_index("ix_model_output_corrections_source_type", "model_output_corrections", ["source_type"])
    op.create_index("ix_model_output_corrections_submitted_by", "model_output_corrections", ["submitted_by"])


def downgrade() -> None:
    op.drop_table("model_output_corrections")
    op.drop_table("knowledge_review_records")
    op.drop_table("knowledge_contributions")
    op.drop_table("device_maintenance_records")
    op.drop_table("uploaded_media")
    op.drop_constraint("fk_maintenance_tasks_sop_execution_id", "maintenance_tasks", type_="foreignkey")
    op.drop_constraint("fk_maintenance_tasks_sop_template_id_sop_templates", "maintenance_tasks", type_="foreignkey")
    op.drop_table("sop_execution_records")
    op.drop_table("sop_templates")

    op.drop_index("ix_model_call_logs_success", table_name="model_call_logs")
    op.drop_index("ix_model_call_logs_call_type", table_name="model_call_logs")
    op.drop_index("ix_model_call_logs_model_name", table_name="model_call_logs")
    op.drop_index("ix_model_call_logs_provider", table_name="model_call_logs")
    op.drop_constraint("fk_model_call_logs_created_by_users", "model_call_logs", type_="foreignkey")
    op.drop_column("model_call_logs", "created_by")
    op.drop_column("model_call_logs", "success")
    op.drop_column("model_call_logs", "latency_ms")
    op.drop_column("model_call_logs", "response")
    op.drop_column("model_call_logs", "prompt")
    op.drop_column("model_call_logs", "call_type")

    op.drop_index("ix_maintenance_tasks_status", table_name="maintenance_tasks")
    op.drop_index("ix_maintenance_tasks_device_id", table_name="maintenance_tasks")
    op.drop_constraint("fk_maintenance_tasks_created_by_users", "maintenance_tasks", type_="foreignkey")
    op.drop_constraint("fk_maintenance_tasks_completed_by_users", "maintenance_tasks", type_="foreignkey")
    op.drop_constraint("fk_maintenance_tasks_assignee_id_users", "maintenance_tasks", type_="foreignkey")
    op.drop_constraint("fk_maintenance_tasks_device_id_devices", "maintenance_tasks", type_="foreignkey")
    op.drop_column("maintenance_tasks", "created_by")
    op.drop_column("maintenance_tasks", "completed_by")
    op.drop_column("maintenance_tasks", "is_recurrent")
    op.drop_column("maintenance_tasks", "verification_result")
    op.drop_column("maintenance_tasks", "replaced_parts")
    op.drop_column("maintenance_tasks", "repair_action")
    op.drop_column("maintenance_tasks", "root_cause")
    op.drop_column("maintenance_tasks", "sop_execution_id")
    op.drop_column("maintenance_tasks", "sop_template_id")
    op.drop_column("maintenance_tasks", "assignee_id")
    op.drop_column("maintenance_tasks", "status")

    op.drop_index("ix_diagnosis_records_model_provider", table_name="diagnosis_records")
    op.drop_index("ix_diagnosis_records_device_id", table_name="diagnosis_records")
    op.drop_constraint("fk_diagnosis_records_created_by_users", "diagnosis_records", type_="foreignkey")
    op.drop_constraint("fk_diagnosis_records_device_id_devices", "diagnosis_records", type_="foreignkey")
    op.drop_column("diagnosis_records", "created_by")
    op.drop_column("diagnosis_records", "model_name")
    op.drop_column("diagnosis_records", "model_provider")
    op.drop_column("diagnosis_records", "media_ids")
    op.drop_column("diagnosis_records", "related_history")
    op.drop_column("diagnosis_records", "device_id")

    op.drop_index("ix_qa_records_model_provider", table_name="qa_records")
    op.drop_index("ix_qa_records_device_id", table_name="qa_records")
    op.drop_constraint("fk_qa_records_created_by_users", "qa_records", type_="foreignkey")
    op.drop_constraint("fk_qa_records_device_id_devices", "qa_records", type_="foreignkey")
    op.drop_column("qa_records", "created_by")
    op.drop_column("qa_records", "model_name")
    op.drop_column("qa_records", "model_provider")
    op.drop_column("qa_records", "related_history")
    op.drop_column("qa_records", "safety_notes")
    op.drop_column("qa_records", "device_id")

    op.drop_column("knowledge_chunks", "content_hash")

    op.drop_index("ix_knowledge_documents_review_status", table_name="knowledge_documents")
    op.drop_constraint("fk_knowledge_documents_reviewed_by_users", "knowledge_documents", type_="foreignkey")
    op.drop_constraint("fk_knowledge_documents_submitted_by_users", "knowledge_documents", type_="foreignkey")
    op.drop_column("knowledge_documents", "review_comment")
    op.drop_column("knowledge_documents", "reviewed_at")
    op.drop_column("knowledge_documents", "reviewed_by")
    op.drop_column("knowledge_documents", "submitted_by")
    op.drop_column("knowledge_documents", "review_status")
    op.drop_column("knowledge_documents", "source_type")

    op.drop_index("ix_devices_model", table_name="devices")
    op.drop_constraint("uq_devices_device_code", "devices", type_="unique")
    op.drop_column("devices", "maintenance_count")
    op.drop_column("devices", "fault_count")
    op.drop_column("devices", "last_maintenance_at")
    op.drop_column("devices", "last_fault_at")
    op.drop_column("devices", "commissioning_date")
    op.drop_column("devices", "device_code")

    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_hash")
