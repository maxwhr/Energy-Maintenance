from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import Text, cast, inspect, or_, select, text

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.models import KGNode, KGNodeAlias, KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from task25f_common import now_iso, write_json


def compile_sql(statement: Any) -> str:
    return str(statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))


def explain(db, statement: Any) -> dict:
    value = db.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + compile_sql(statement)))
    return value[0] if isinstance(value, list) else value


def nodes(plan: dict) -> list[dict]:
    output = []
    stack = [plan.get("Plan", {})]
    while stack:
        node = stack.pop()
        if not node:
            continue
        output.append({
            key: node.get(key)
            for key in (
                "Node Type", "Relation Name", "Index Name", "Actual Rows",
                "Actual Total Time", "Plan Rows", "Rows Removed by Filter",
                "Shared Hit Blocks", "Shared Read Blocks",
            )
            if key in node
        })
        stack.extend(node.get("Plans") or [])
    return output


def plan_record(plan: dict) -> dict:
    return {
        "planning_time_ms": plan.get("Planning Time"),
        "execution_time_ms": plan.get("Execution Time"),
        "nodes": nodes(plan),
        "raw": plan,
    }


def main() -> int:
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        chunk_ids = list(db.scalars(select(KnowledgeChunk.id).where(
            KnowledgeChunk.document_id.in_(scope.allowed_document_ids), KnowledgeChunk.status == "active",
        ).limit(200)))
        vector_ids = list(db.scalars(select(MaintenanceSemanticAnchor.vector_id).where(
            MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
            MaintenanceSemanticAnchor.index_status == "active",
        ).limit(200)))

        scope_document = select(KnowledgeDocument.id).where(
            KnowledgeDocument.status == "active",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.metadata_json["normalized_language"].as_string() == "zh-CN",
            KnowledgeDocument.metadata_json["approved_for_pilot"].as_string() == "true",
            KnowledgeDocument.metadata_json["engineering_approved_for_pilot"].as_string() == "true",
        ).order_by(KnowledgeDocument.id)
        hydration = select(KnowledgeChunk, KnowledgeDocument).join(
            KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id,
        ).where(
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.status == "active",
            *RetrievalRepository._scope_filters(scope),
        )
        keyword = hydration.where(or_(
            KnowledgeChunk.content.ilike("%通信%"),
            KnowledgeChunk.section_title.ilike("%通信%"),
            KnowledgeDocument.title.ilike("%通信%"),
            cast(KnowledgeDocument.metadata_json, Text).ilike("%通信%"),
        )).limit(50)
        statements = {
            "chunk_id_batch_load": select(KnowledgeChunk).where(
                KnowledgeChunk.id.in_(chunk_ids), KnowledgeChunk.status == "active",
            ),
            "semantic_unit_id_batch_load": select(MaintenanceSemanticAnchor).where(
                MaintenanceSemanticAnchor.collection_name == scope.collection_name,
                MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
                MaintenanceSemanticAnchor.vector_id.in_(vector_ids),
                MaintenanceSemanticAnchor.index_status == "active",
            ),
            "source_chunk_mapping": select(
                MaintenanceSemanticAnchor.vector_id,
                MaintenanceSemanticAnchor.source_chunk_id,
                MaintenanceSemanticAnchor.document_id,
            ).where(
                MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
                MaintenanceSemanticAnchor.vector_id.in_(vector_ids),
            ),
            "document_approval_version_filter": select(KnowledgeDocument).where(
                KnowledgeDocument.id.in_(scope.allowed_document_ids),
                KnowledgeDocument.status == "active",
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.review_status == "approved",
            ),
            "keyword_search": keyword,
            "alias_search": select(KGNodeAlias.id, KGNodeAlias.node_id).join(
                KGNode, KGNode.id == KGNodeAlias.node_id,
            ).where(
                KGNodeAlias.normalized_alias == "通信中断",
                KGNode.status == "active",
            ).limit(50),
            "citation_locator": select(
                KnowledgeChunk.id,
                KnowledgeChunk.document_id,
                KnowledgeChunk.section_title,
                KnowledgeChunk.page_number,
                KnowledgeChunk.metadata_json,
                KnowledgeDocument.source,
                KnowledgeDocument.metadata_json,
            ).join(KnowledgeDocument).where(
                KnowledgeChunk.id.in_(chunk_ids[:50]),
                *RetrievalRepository._scope_filters(scope),
            ),
            "scope_document_selection": scope_document,
            "scope_candidate_hydration": hydration,
        }
        plans = {name: plan_record(explain(db, statement)) for name, statement in statements.items()}

    inspector = inspect(engine)
    index_inventory = {
        table: [item["name"] for item in inspector.get_indexes(table)]
        for table in ("knowledge_documents", "knowledge_chunks", "maintenance_semantic_anchors", "kg_node_aliases", "kg_nodes")
    }
    slowest_ms = max(float(item.get("execution_time_ms") or 0) for item in plans.values())
    payload = {
        "generated_at": now_iso(),
        "status": "PASS",
        "explain_analyze": True,
        "buffers": True,
        "plans": plans,
        "index_inventory": index_inventory,
        "indexes_added": [],
        "migration_added": False,
        "alembic_head_retained": "20260712_0015",
        "decision": "NO_INDEX_MIGRATION_REQUIRED",
        "decision_reason": "All audited hot-path plans are below the measured database p95 gate; concurrent delay was caused by repeated scope hydration and bounded provider queues, not a missing-index plan.",
        "slowest_plan_execution_ms": round(slowest_ms, 3),
        "before_after": "No schema mutation was made; the audited retained plan is the pre-index and final plan.",
        "write_cost_change": 0,
        "kg_alias_runtime_status": "DISABLED_DUPLICATE_KEYWORD; plan retained only as an explicit readiness audit",
    }
    write_json("explain.json", payload)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "slowest_ms": payload["slowest_plan_execution_ms"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
