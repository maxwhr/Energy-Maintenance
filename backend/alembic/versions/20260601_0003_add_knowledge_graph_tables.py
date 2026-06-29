"""add_knowledge_graph_tables

Revision ID: 20260601_0003
Revises: 20260601_0002
Create Date: 2026-06-20 18:03:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0003"
down_revision: Union[str, None] = "20260601_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_col(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "kg_nodes",
        _uuid_col("id", nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=32), nullable=True),
        sa.Column("product_series", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=32), server_default="pv_inverter", nullable=False),
        sa.Column("properties_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        _uuid_col("source_id"),
        _uuid_col("created_by"),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "node_type",
            "canonical_name",
            "manufacturer",
            "product_series",
            "device_type",
            name="uq_kg_nodes_identity",
        ),
    )
    op.create_index("ix_kg_nodes_node_type", "kg_nodes", ["node_type"])
    op.create_index("ix_kg_nodes_canonical_name", "kg_nodes", ["canonical_name"])
    op.create_index("ix_kg_nodes_manufacturer", "kg_nodes", ["manufacturer"])
    op.create_index("ix_kg_nodes_product_series", "kg_nodes", ["product_series"])
    op.create_index("ix_kg_nodes_device_type", "kg_nodes", ["device_type"])
    op.create_index("ix_kg_nodes_status", "kg_nodes", ["status"])
    op.create_index("ix_kg_nodes_created_at", "kg_nodes", ["created_at"])

    op.create_table(
        "kg_edges",
        _uuid_col("id", nullable=False),
        _uuid_col("source_node_id", nullable=False),
        _uuid_col("target_node_id", nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("display_relation", sa.String(length=128), nullable=True),
        sa.Column("properties_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        _uuid_col("source_id"),
        _uuid_col("created_by"),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_node_id"], ["kg_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["kg_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_node_id", "target_node_id", "relation_type", name="uq_kg_edges_identity"),
    )
    op.create_index("ix_kg_edges_source_node_id", "kg_edges", ["source_node_id"])
    op.create_index("ix_kg_edges_target_node_id", "kg_edges", ["target_node_id"])
    op.create_index("ix_kg_edges_relation_type", "kg_edges", ["relation_type"])
    op.create_index("ix_kg_edges_status", "kg_edges", ["status"])
    op.create_index("ix_kg_edges_created_at", "kg_edges", ["created_at"])

    op.create_table(
        "kg_node_aliases",
        _uuid_col("id", nullable=False),
        _uuid_col("node_id", nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        _uuid_col("source_id"),
        _created_at(),
        sa.ForeignKeyConstraint(["node_id"], ["kg_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id", "normalized_alias", name="uq_kg_node_aliases_node_alias"),
    )
    op.create_index("ix_kg_node_aliases_node_id", "kg_node_aliases", ["node_id"])
    op.create_index("ix_kg_node_aliases_normalized_alias", "kg_node_aliases", ["normalized_alias"])

    op.create_table(
        "kg_extraction_runs",
        _uuid_col("id", nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        _uuid_col("source_id"),
        sa.Column("extractor", sa.String(length=64), server_default="rule_based_v1", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("candidate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("approved_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _uuid_col("created_by"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kg_extraction_runs_source_type", "kg_extraction_runs", ["source_type"])
    op.create_index("ix_kg_extraction_runs_source_id", "kg_extraction_runs", ["source_id"])
    op.create_index("ix_kg_extraction_runs_status", "kg_extraction_runs", ["status"])
    op.create_index("ix_kg_extraction_runs_created_by", "kg_extraction_runs", ["created_by"])
    op.create_index("ix_kg_extraction_runs_created_at", "kg_extraction_runs", ["created_at"])

    op.create_table(
        "kg_candidates",
        _uuid_col("id", nullable=False),
        _uuid_col("run_id", nullable=False),
        sa.Column("candidate_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.6", nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        _uuid_col("approved_node_id"),
        _uuid_col("approved_edge_id"),
        _uuid_col("reviewed_by"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["approved_edge_id"], ["kg_edges.id"]),
        sa.ForeignKeyConstraint(["approved_node_id"], ["kg_nodes.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["kg_extraction_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kg_candidates_run_id", "kg_candidates", ["run_id"])
    op.create_index("ix_kg_candidates_candidate_type", "kg_candidates", ["candidate_type"])
    op.create_index("ix_kg_candidates_status", "kg_candidates", ["status"])
    op.create_index("ix_kg_candidates_reviewed_by", "kg_candidates", ["reviewed_by"])
    op.create_index("ix_kg_candidates_created_at", "kg_candidates", ["created_at"])

    op.create_table(
        "kg_evidence_links",
        _uuid_col("id", nullable=False),
        _uuid_col("node_id"),
        _uuid_col("edge_id"),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        _uuid_col("source_id"),
        _uuid_col("document_id"),
        _uuid_col("chunk_id"),
        _uuid_col("contribution_id"),
        sa.Column("diagnosis_trace_id", sa.String(length=64), nullable=True),
        _uuid_col("task_id"),
        _uuid_col("maintenance_record_id"),
        _uuid_col("media_id"),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        _created_at(),
        sa.CheckConstraint("node_id IS NOT NULL OR edge_id IS NOT NULL", name="ck_kg_evidence_links_target_present"),
        sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.id"]),
        sa.ForeignKeyConstraint(["contribution_id"], ["knowledge_contributions.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.ForeignKeyConstraint(["edge_id"], ["kg_edges.id"]),
        sa.ForeignKeyConstraint(["maintenance_record_id"], ["device_maintenance_records.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["uploaded_media.id"]),
        sa.ForeignKeyConstraint(["node_id"], ["kg_nodes.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kg_evidence_links_node_id", "kg_evidence_links", ["node_id"])
    op.create_index("ix_kg_evidence_links_edge_id", "kg_evidence_links", ["edge_id"])
    op.create_index("ix_kg_evidence_links_source_type", "kg_evidence_links", ["source_type"])
    op.create_index("ix_kg_evidence_links_source_id", "kg_evidence_links", ["source_id"])
    op.create_index("ix_kg_evidence_links_document_id", "kg_evidence_links", ["document_id"])
    op.create_index("ix_kg_evidence_links_chunk_id", "kg_evidence_links", ["chunk_id"])
    op.create_index("ix_kg_evidence_links_contribution_id", "kg_evidence_links", ["contribution_id"])
    op.create_index("ix_kg_evidence_links_diagnosis_trace_id", "kg_evidence_links", ["diagnosis_trace_id"])
    op.create_index("ix_kg_evidence_links_task_id", "kg_evidence_links", ["task_id"])
    op.create_index("ix_kg_evidence_links_media_id", "kg_evidence_links", ["media_id"])
    op.create_index("ix_kg_evidence_links_created_at", "kg_evidence_links", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_kg_evidence_links_created_at", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_media_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_task_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_diagnosis_trace_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_contribution_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_chunk_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_document_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_source_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_source_type", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_edge_id", table_name="kg_evidence_links")
    op.drop_index("ix_kg_evidence_links_node_id", table_name="kg_evidence_links")
    op.drop_table("kg_evidence_links")

    op.drop_index("ix_kg_candidates_created_at", table_name="kg_candidates")
    op.drop_index("ix_kg_candidates_reviewed_by", table_name="kg_candidates")
    op.drop_index("ix_kg_candidates_status", table_name="kg_candidates")
    op.drop_index("ix_kg_candidates_candidate_type", table_name="kg_candidates")
    op.drop_index("ix_kg_candidates_run_id", table_name="kg_candidates")
    op.drop_table("kg_candidates")

    op.drop_index("ix_kg_extraction_runs_created_at", table_name="kg_extraction_runs")
    op.drop_index("ix_kg_extraction_runs_created_by", table_name="kg_extraction_runs")
    op.drop_index("ix_kg_extraction_runs_status", table_name="kg_extraction_runs")
    op.drop_index("ix_kg_extraction_runs_source_id", table_name="kg_extraction_runs")
    op.drop_index("ix_kg_extraction_runs_source_type", table_name="kg_extraction_runs")
    op.drop_table("kg_extraction_runs")

    op.drop_index("ix_kg_node_aliases_normalized_alias", table_name="kg_node_aliases")
    op.drop_index("ix_kg_node_aliases_node_id", table_name="kg_node_aliases")
    op.drop_table("kg_node_aliases")

    op.drop_index("ix_kg_edges_created_at", table_name="kg_edges")
    op.drop_index("ix_kg_edges_status", table_name="kg_edges")
    op.drop_index("ix_kg_edges_relation_type", table_name="kg_edges")
    op.drop_index("ix_kg_edges_target_node_id", table_name="kg_edges")
    op.drop_index("ix_kg_edges_source_node_id", table_name="kg_edges")
    op.drop_table("kg_edges")

    op.drop_index("ix_kg_nodes_created_at", table_name="kg_nodes")
    op.drop_index("ix_kg_nodes_status", table_name="kg_nodes")
    op.drop_index("ix_kg_nodes_device_type", table_name="kg_nodes")
    op.drop_index("ix_kg_nodes_product_series", table_name="kg_nodes")
    op.drop_index("ix_kg_nodes_manufacturer", table_name="kg_nodes")
    op.drop_index("ix_kg_nodes_canonical_name", table_name="kg_nodes")
    op.drop_index("ix_kg_nodes_node_type", table_name="kg_nodes")
    op.drop_table("kg_nodes")
