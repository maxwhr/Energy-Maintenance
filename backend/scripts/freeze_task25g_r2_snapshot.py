from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from task25g_r2_common import (
    BACKEND,
    EXPECTED_ALEMBIC_REVISION,
    RUNTIME,
    TASK25G_R1_REPORT,
    TASK25G_R1_RUNTIME,
    TASK25G_REPORT,
    TASK25G_RUNTIME,
    alembic_state,
    directory_manifest,
    git_snapshot,
    now_iso,
    public_path,
    sha256_file,
    sha256_text,
    sha256_value,
    vector_namespace_counts,
    write_json,
    zip_inventory,
)


OUTPUTS = (
    RUNTIME / "snapshot.json",
    RUNTIME / "hash_manifest.json",
    RUNTIME / "active_fact_baseline.json",
    RUNTIME / "current_chinese_corpus_manifest.json",
)


def _required_sources() -> dict[str, Any]:
    required = [
        TASK25G_REPORT,
        TASK25G_R1_REPORT,
        TASK25G_RUNTIME / "kg_inventory.json",
        TASK25G_RUNTIME / "kg_scope_and_evidence.json",
        TASK25G_R1_RUNTIME / "task25g_snapshot.json",
        TASK25G_R1_RUNTIME / "hash_manifest.json",
        TASK25G_R1_RUNTIME / "reconciliation.json",
        TASK25G_R1_RUNTIME / "regression.json",
    ]
    missing = [public_path(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"required frozen Task 25G/R1 inputs are missing: {missing}")
    return {
        "task25g_report": {
            "path": public_path(TASK25G_REPORT),
            "size": TASK25G_REPORT.stat().st_size,
            "sha256": sha256_file(TASK25G_REPORT),
        },
        "task25g_r1_report": {
            "path": public_path(TASK25G_R1_REPORT),
            "size": TASK25G_R1_REPORT.stat().st_size,
            "sha256": sha256_file(TASK25G_R1_REPORT),
        },
        "task25g_runtime": directory_manifest(TASK25G_RUNTIME),
        "task25g_r1_runtime": directory_manifest(TASK25G_R1_RUNTIME),
    }


def _fact_baseline(session: Any) -> dict[str, Any]:
    from app.models import KGEdge, KGEvidenceLink, KGNode

    nodes = list(
        session.scalars(
            select(KGNode)
            .where(KGNode.status == "active")
            .order_by(KGNode.id)
        )
    )
    edges = list(
        session.scalars(
            select(KGEdge)
            .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node))
            .where(KGEdge.status == "active")
            .order_by(KGEdge.id)
        )
    )
    evidence = list(session.scalars(select(KGEvidenceLink).order_by(KGEvidenceLink.id)))
    node_rows = [
        {
            "fact_id": f"node:{node.id}",
            "node_id": str(node.id),
            "node_type": node.node_type,
            "canonical_name": node.canonical_name,
            "manufacturer": node.manufacturer,
            "product_series": node.product_series,
            "device_type": node.device_type,
            "status": node.status,
            "properties_sha256": sha256_value(node.properties_json or {}),
        }
        for node in nodes
    ]
    edge_rows = [
        {
            "fact_id": f"edge:{edge.id}",
            "edge_id": str(edge.id),
            "source_node_id": str(edge.source_node_id),
            "source_node_type": edge.source_node.node_type,
            "source_canonical_name": edge.source_node.canonical_name,
            "relation_type": edge.relation_type,
            "target_node_id": str(edge.target_node_id),
            "target_node_type": edge.target_node.node_type,
            "target_canonical_name": edge.target_node.canonical_name,
            "status": edge.status,
            "properties_sha256": sha256_value(edge.properties_json or {}),
        }
        for edge in edges
    ]
    evidence_rows = [
        {
            "evidence_id": str(item.id),
            "node_id": str(item.node_id) if item.node_id else None,
            "edge_id": str(item.edge_id) if item.edge_id else None,
            "source_type": item.source_type,
            "source_id": str(item.source_id) if item.source_id else None,
            "document_id": str(item.document_id) if item.document_id else None,
            "chunk_id": str(item.chunk_id) if item.chunk_id else None,
            "confidence": item.confidence,
            "evidence_text_sha256": sha256_text(item.evidence_text),
        }
        for item in evidence
    ]
    payload = {
        "version": "task25g_r2_active_fact_baseline_v1",
        "created_at": now_iso(),
        "active_fact_count": len(node_rows) + len(edge_rows),
        "active_node_count": len(node_rows),
        "active_edge_count": len(edge_rows),
        "historical_evidence_count": len(evidence_rows),
        "nodes": node_rows,
        "edges": edge_rows,
        "evidence": evidence_rows,
    }
    payload["baseline_sha256"] = sha256_value(payload)
    return payload


def _current_corpus(session: Any) -> dict[str, Any]:
    from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor

    document_filters = (
        KnowledgeDocument.status == "active",
        KnowledgeDocument.review_status == "approved",
        KnowledgeDocument.parse_status == "parsed",
        KnowledgeDocument.metadata_json["normalized_language"].as_string() == "zh-CN",
        KnowledgeDocument.metadata_json["engineering_approved_for_pilot"].as_string() == "true",
        KnowledgeDocument.metadata_json["approved_for_pilot"].as_string() == "true",
    )
    documents = list(
        session.scalars(
            select(KnowledgeDocument)
            .where(*document_filters)
            .order_by(KnowledgeDocument.id)
        )
    )
    documents = [
        item
        for item in documents
        if bool((item.metadata_json or {}).get("current_version", True))
        and not (item.metadata_json or {}).get("superseded_by_document_id")
        and item.document_type != "marketing"
    ]
    document_ids = [item.id for item in documents]
    chunks = list(
        session.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id.in_(document_ids), KnowledgeChunk.status == "active")
            .order_by(KnowledgeChunk.document_id, KnowledgeChunk.chunk_index, KnowledgeChunk.id)
        )
    )
    anchors = list(
        session.scalars(
            select(MaintenanceSemanticAnchor)
            .where(
                MaintenanceSemanticAnchor.document_id.in_(document_ids),
                MaintenanceSemanticAnchor.language == "zh-CN",
                MaintenanceSemanticAnchor.current_version.is_(True),
                MaintenanceSemanticAnchor.semantic_representation_version
                == "task25b_r3_dev_r5_semantic_unit_v2",
            )
            .order_by(MaintenanceSemanticAnchor.id)
        )
    )
    units: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        unit = (anchor.semantic_fields or {}).get("semantic_unit") or {}
        unit_id = str(unit.get("semantic_unit_id") or (anchor.semantic_fields or {}).get("semantic_unit_id") or "")
        if not unit_id:
            continue
        units.setdefault(
            unit_id,
            {
                "semantic_unit_id": unit_id,
                "semantic_unit_type": unit.get("semantic_unit_type") or unit.get("unit_type"),
                "document_id": str(anchor.document_id),
                "source_chunk_ids": [str(value) for value in unit.get("source_chunk_ids") or []],
                "source_locator": unit.get("source_locator") or anchor.source_locator or {},
                "canonical_text_hash": unit.get("canonical_text_hash"),
                "source_span_hash": unit.get("source_span_hash"),
                "stable_unit_key": unit.get("stable_unit_key"),
                "quality_status": unit.get("quality_status"),
                "engineering_verified": bool(unit.get("engineering_verified")),
                "expert_verified": bool(unit.get("expert_verified")),
                "payload_sha256": sha256_value(unit),
            },
        )
    document_rows = [
        {
            "document_id": str(item.id),
            "title": item.title,
            "manufacturer": item.manufacturer,
            "product_series": item.product_series,
            "model": item.model,
            "document_type": item.document_type,
            "review_status": item.review_status,
            "status": item.status,
            "parse_status": item.parse_status,
            "language": (item.metadata_json or {}).get("normalized_language"),
            "approval_mode": (item.metadata_json or {}).get("approval_mode"),
            "current_version": bool((item.metadata_json or {}).get("current_version", True)),
            "metadata_sha256": sha256_value(item.metadata_json or {}),
        }
        for item in documents
    ]
    chunk_rows = [
        {
            "chunk_id": str(item.id),
            "document_id": str(item.document_id),
            "chunk_index": item.chunk_index,
            "section_title": item.section_title,
            "page_number": item.page_number,
            "content_sha256": sha256_text(item.content),
            "metadata_sha256": sha256_value(item.metadata_json or {}),
            "source_locator": (item.metadata_json or {}).get("source_locator") or {},
        }
        for item in chunks
    ]
    payload = {
        "version": "task25g_r2_current_chinese_corpus_manifest_v1",
        "created_at": now_iso(),
        "scope": {
            "language": "zh-CN",
            "lifecycle": "active/current",
            "review_status": "approved",
            "parse_status": "parsed",
            "engineering_approved_for_pilot": True,
            "approved_for_pilot": True,
            "marketing_excluded": True,
        },
        "document_count": len(document_rows),
        "chunk_count": len(chunk_rows),
        "semantic_unit_count": len(units),
        "documents": document_rows,
        "chunks": chunk_rows,
        "semantic_units": sorted(units.values(), key=lambda item: item["semantic_unit_id"]),
    }
    payload["corpus_sha256"] = sha256_value(
        {
            "documents": document_rows,
            "chunks": chunk_rows,
            "semantic_units": payload["semantic_units"],
        }
    )
    return payload


def _production_baseline(session: Any, fact_baseline: dict[str, Any]) -> dict[str, Any]:
    from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService

    node_ids = [item["node_id"] for item in fact_baseline["nodes"]]
    edge_ids = [item["edge_id"] for item in fact_baseline["edges"]]
    scope = KnowledgeGraphProductionScopeService(session).evaluate(node_ids=node_ids, edge_ids=edge_ids)
    return {
        "eligible_node_count": len(scope.eligible_node_ids),
        "eligible_edge_count": len(scope.eligible_edge_ids),
        "current_evidence_count": len(scope.all_evidence()),
        "empty_context": not scope.eligible_node_ids and not scope.eligible_edge_ids,
        "excluded_evidence_count": len(scope.excluded_evidence),
    }


def main() -> int:
    if any(path.exists() for path in OUTPUTS):
        raise SystemExit("Task 25G-R2 snapshot already exists; refusing to overwrite")
    if str(os.environ.get("TASK25B_ALLOW_FULL_REINDEX", "false")).lower() not in {"", "0", "false", "no"}:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")

    from app.core.database import SessionLocal
    from app.models import KGCandidate

    required_sources = _required_sources()
    alembic = alembic_state()
    if EXPECTED_ALEMBIC_REVISION not in alembic.get("current", ""):
        raise RuntimeError(f"unexpected Alembic current: {alembic.get('current')}")

    with SessionLocal() as session:
        facts = _fact_baseline(session)
        corpus = _current_corpus(session)
        if facts["active_fact_count"] != 68:
            raise RuntimeError(f"expected 68 active facts, found {facts['active_fact_count']}")
        if facts["historical_evidence_count"] != 76:
            raise RuntimeError(f"expected 76 historical evidence rows, found {facts['historical_evidence_count']}")
        if (corpus["document_count"], corpus["chunk_count"], corpus["semantic_unit_count"]) != (16, 1262, 2508):
            raise RuntimeError(
                "current Chinese corpus drifted: "
                f"{corpus['document_count']}/{corpus['chunk_count']}/{corpus['semantic_unit_count']}"
            )
        pending_candidates = list(
            session.scalars(
                select(KGCandidate).where(
                    KGCandidate.candidate_type == "grounding_remediation",
                    KGCandidate.status == "pending",
                )
            )
        )
        if len(pending_candidates) != 2:
            raise RuntimeError(f"expected 2 pending R1 remediation candidates, found {len(pending_candidates)}")
        production = _production_baseline(session, facts)
        vectors = vector_namespace_counts(session)

    env_path = BACKEND / ".env"
    hash_manifest = {
        "version": "task25g_r2_hash_manifest_v1",
        "created_at": now_iso(),
        "task25g_and_r1": required_sources,
        "backend_env": {
            "path": public_path(env_path),
            "exists": env_path.is_file(),
            "sha256": sha256_file(env_path),
            "values_recorded": False,
        },
        "active_fact_baseline_sha256": facts["baseline_sha256"],
        "current_chinese_corpus_sha256": corpus["corpus_sha256"],
    }
    hash_manifest["manifest_sha256"] = sha256_value(hash_manifest)
    snapshot = {
        "version": "task25g_r2_snapshot_v1",
        "created_at": now_iso(),
        "r1_status": "TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT",
        "alembic": alembic,
        "expected_alembic_revision": EXPECTED_ALEMBIC_REVISION,
        "database": {
            "status": "AVAILABLE",
            "active_facts": facts["active_fact_count"],
            "historical_evidence": facts["historical_evidence_count"],
            "pending_r1_remediation_candidates": 2,
            "production_scope": production,
            "vector_namespaces": vectors,
        },
        "corpus": {
            "documents": corpus["document_count"],
            "chunks": corpus["chunk_count"],
            "semantic_units": corpus["semantic_unit_count"],
        },
        "git": git_snapshot(),
        "zip_inventory": zip_inventory(),
        "hash_manifest_sha256": hash_manifest["manifest_sha256"],
        "boundaries": {
            "task25g_runtime_writes": 0,
            "task25g_r1_runtime_writes": 0,
            "task25g_report_writes": 0,
            "task25g_r1_report_writes": 0,
            "database_writes": 0,
            "document_content_writes": 0,
            "chunk_writes": 0,
            "semantic_unit_writes": 0,
            "embedding_calls": 0,
            "vector_writes": 0,
            "full_reindex": False,
            "package_generated": False,
            "git_mutation": False,
            "expert_auto_write": False,
            "real_machine_acceptance_executed": False,
        },
    }

    RUNTIME.mkdir(parents=True, exist_ok=False)
    write_json("active_fact_baseline.json", facts, overwrite=False)
    write_json("current_chinese_corpus_manifest.json", corpus, overwrite=False)
    write_json("hash_manifest.json", hash_manifest, overwrite=False)
    write_json("snapshot.json", snapshot, overwrite=False)
    print(
        json.dumps(
            {
                "status": "TASK25G_R2_SNAPSHOT_FROZEN",
                "active_facts": facts["active_fact_count"],
                "historical_evidence": facts["historical_evidence_count"],
                "current_chinese_documents": corpus["document_count"],
                "current_chinese_chunks": corpus["chunk_count"],
                "semantic_units": corpus["semantic_unit_count"],
                "production_scope": production,
                "alembic_current": alembic["current"],
                "staged_files": len(snapshot["git"]["staged_files"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
