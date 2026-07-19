from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import bindparam, text

from task25g_r1_common import RUNTIME, now_iso, read_json, sha256_text, write_csv, write_json


CSV_FIELDS = [
    "evidence_id",
    "fact_type",
    "node_id",
    "edge_id",
    "fact_status",
    "source_document_id",
    "source_document_title_hash",
    "source_document_category",
    "source_document_language",
    "source_document_approval_status",
    "source_document_lifecycle_status",
    "source_document_version",
    "source_document_current_flag",
    "source_document_superseded_by",
    "source_chunk_id",
    "source_semantic_unit_id",
    "source_locator",
    "extraction_run_id",
    "candidate_id",
    "conversion_record_id",
    "created_at",
    "updated_at",
    "production_context_usage",
    "rag_context_usage",
    "diagnosis_usage",
    "preliminary_classification",
]


def _baseline_ids() -> list[str]:
    baseline = read_json("leakage_baseline.json", {})
    values = [str(value) for value in baseline.get("evidence_ids") or []]
    if len(values) != 12:
        raise RuntimeError(f"expected 12 frozen evidence IDs, found {len(values)}")
    return values


def _source_locator(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("chunk_metadata") or {}
    locator = metadata.get("source_locator")
    if not isinstance(locator, dict):
        locator = {}
    return {
        "page_number": row.get("page_number") or locator.get("page_number"),
        "section_title_hash": sha256_text(row.get("section_title") or locator.get("section_title")),
        "chunk_index": row.get("chunk_index"),
        "locator_type": locator.get("locator_type") or "knowledge_chunk",
    }


def _document_state(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("document_metadata") or {}
    lifecycle = str(row.get("document_lifecycle_status") or "").lower()
    review = str(row.get("source_document_approval_status") or "").lower()
    category = str(row.get("source_document_category") or "").lower()
    language = str(metadata.get("normalized_language") or metadata.get("language") or "").lower()
    superseded_by = metadata.get("superseded_by_document_id")
    metadata_current = metadata.get("current_version", True)
    current = lifecycle == "active" and bool(metadata_current) and not superseded_by
    approval_mode = str(metadata.get("approval_mode") or "").lower()
    engineering_approved = review == "approved" and approval_mode in {
        "development_engineering_auto",
        "human_expert_approval",
        "engineering_approved",
        "",
    }
    return {
        "language": language or None,
        "version": metadata.get("version") or metadata.get("document_version") or metadata.get("revision"),
        "current": current,
        "superseded_by": str(superseded_by) if superseded_by else None,
        "pending": review in {"draft", "pending", "pending_review", "unreviewed", ""},
        "archived": lifecycle == "archived",
        "superseded": lifecycle == "superseded" or bool(superseded_by),
        "marketing": category == "marketing" or str(metadata.get("source_classification") or "").lower() == "marketing",
        "english": language in {"en", "en-us", "en-gb", "english"},
        "approval_invalid": not engineering_approved,
        "approval_mode": approval_mode or None,
    }


def _usage_count(session: Any, table: str, columns: list[str], evidence_id: str) -> int:
    total = 0
    for column in columns:
        total += int(
            session.scalar(
                text(f'SELECT count(*) FROM "{table}" WHERE coalesce("{column}"::text, \'\') LIKE :needle'),
                {"needle": f"%{evidence_id}%"},
            )
            or 0
        )
    return total


def _runtime_context_usage(session: Any, row: dict[str, Any]) -> dict[str, Any]:
    from app.services.knowledge_graph_service import KnowledgeGraphService

    term = row.get("fact_search_term")
    if not term:
        return {"checked": False, "returned": False, "reason": "fact_search_term_missing"}
    try:
        context = KnowledgeGraphService(session).business_context(question=str(term), limit=30)
    except Exception as exc:  # noqa: BLE001 - evidence audit records the boundary without leaking data.
        return {"checked": True, "returned": False, "error_type": exc.__class__.__name__}
    returned_ids = {str(item.get("id")) for item in context.get("evidence") or [] if isinstance(item, dict)}
    return {
        "checked": True,
        "returned": str(row["evidence_id"]) in returned_ids,
        "returned_evidence_count": len(returned_ids),
    }


def _preliminary_classification(row: dict[str, Any], valid_current_evidence_count: int) -> str:
    state = row["state"]
    if state["archived"] and row["source_document_category"] == "maintenance_record":
        if valid_current_evidence_count > 0:
            return "DUPLICATE_OLD_EVIDENCE"
        return "HISTORICAL_MAINTENANCE_RECORD_ONLY"
    if valid_current_evidence_count > 0:
        return "DUPLICATE_OLD_EVIDENCE"
    if state["archived"]:
        return "NO_CURRENT_SUCCESSOR"
    return "UNKNOWN"


def main() -> int:
    from app.core.database import SessionLocal

    evidence_ids = _baseline_ids()
    statement = text(
        """
        SELECT ev.id::text AS evidence_id,
               ev.node_id::text AS node_id,
               ev.edge_id::text AS edge_id,
               ev.document_id::text AS source_document_id,
               ev.chunk_id::text AS source_chunk_id,
               ev.source_type,
               ev.source_id::text AS source_id,
               ev.created_at,
               n.node_type,
               n.canonical_name AS node_name,
               n.status AS node_status,
               e.relation_type,
               e.status AS edge_status,
               sn.canonical_name AS source_node_name,
               tn.canonical_name AS target_node_name,
               d.title AS source_document_title,
               d.document_type AS source_document_category,
               d.review_status AS source_document_approval_status,
               d.status AS document_lifecycle_status,
               d.parse_status AS document_parse_status,
               d.metadata_json AS document_metadata,
               d.manufacturer,
               d.product_series,
               d.model AS device_model,
               c.chunk_index,
               c.page_number,
               c.section_title,
               c.metadata_json AS chunk_metadata,
               sa.id::text AS semantic_unit_id,
               candidate.id::text AS candidate_id,
               candidate.run_id::text AS extraction_run_id,
               conversion.id::text AS conversion_record_id
        FROM kg_evidence_links ev
        LEFT JOIN kg_nodes n ON n.id=ev.node_id
        LEFT JOIN kg_edges e ON e.id=ev.edge_id
        LEFT JOIN kg_nodes sn ON sn.id=e.source_node_id
        LEFT JOIN kg_nodes tn ON tn.id=e.target_node_id
        LEFT JOIN knowledge_documents d ON d.id=ev.document_id
        LEFT JOIN knowledge_chunks c ON c.id=ev.chunk_id
        LEFT JOIN LATERAL (
            SELECT a.id
            FROM maintenance_semantic_anchors a
            WHERE a.source_chunk_id=ev.chunk_id
            ORDER BY a.current_version DESC, a.created_at DESC
            LIMIT 1
        ) sa ON true
        LEFT JOIN LATERAL (
            SELECT kc.id, kc.run_id
            FROM kg_candidates kc
            WHERE (ev.node_id IS NOT NULL AND kc.approved_node_id=ev.node_id)
               OR (ev.edge_id IS NOT NULL AND kc.approved_edge_id=ev.edge_id)
            ORDER BY kc.created_at DESC
            LIMIT 1
        ) candidate ON true
        LEFT JOIN LATERAL (
            SELECT ac.id
            FROM agent_artifact_conversions ac
            WHERE ac.target_id=ev.document_id
            ORDER BY ac.created_at DESC
            LIMIT 1
        ) conversion ON true
        WHERE ev.id::text IN :evidence_ids
        ORDER BY ev.id::text
        """
    ).bindparams(bindparam("evidence_ids", expanding=True))

    output: list[dict[str, Any]] = []
    with SessionLocal() as session:
        raw_rows = [dict(row) for row in session.execute(statement, {"evidence_ids": evidence_ids}).mappings()]
        if len(raw_rows) != 12:
            raise RuntimeError(f"expected 12 forensic rows, found {len(raw_rows)}")

        for row in raw_rows:
            state = _document_state(row)
            fact_filter = "node_id=:fact_id" if row.get("node_id") else "edge_id=:fact_id"
            fact_id = row.get("node_id") or row.get("edge_id")
            valid_current_evidence_count = int(
                session.scalar(
                    text(
                        f"""
                        SELECT count(*)
                        FROM kg_evidence_links other
                        JOIN knowledge_documents current_doc ON current_doc.id=other.document_id
                        LEFT JOIN knowledge_chunks current_chunk ON current_chunk.id=other.chunk_id
                        WHERE other.{fact_filter}
                          AND other.id::text<>:evidence_id
                          AND current_doc.status='active'
                          AND current_doc.review_status='approved'
                          AND current_doc.parse_status='parsed'
                          AND current_doc.document_type<>'marketing'
                          AND coalesce(current_doc.metadata_json->>'normalized_language', '')='zh-CN'
                          AND coalesce(current_doc.metadata_json->>'current_version', 'true')='true'
                          AND coalesce(current_doc.metadata_json->>'superseded_by_document_id', '')=''
                          AND coalesce(current_doc.metadata_json->>'approval_mode', '') IN
                              ('development_engineering_auto','human_expert_approval','engineering_approved')
                          AND (other.chunk_id IS NULL OR current_chunk.status='active')
                        """
                    ),
                    {"fact_id": fact_id, "evidence_id": row["evidence_id"]},
                )
                or 0
            )
            fact_type = f"node:{row['node_type']}" if row.get("node_id") else f"edge:{row['relation_type']}"
            fact_status = row.get("node_status") if row.get("node_id") else row.get("edge_status")
            row["fact_search_term"] = row.get("node_name") or row.get("source_node_name") or row.get("target_node_name")
            runtime_usage = _runtime_context_usage(session, row)
            qa_usage = _usage_count(session, "qa_records", ["references", "retrieved_chunks", "related_history"], row["evidence_id"])
            diagnosis_usage = _usage_count(
                session,
                "diagnosis_records",
                ["references", "related_history"],
                row["evidence_id"],
            )
            item = {
                "evidence_id": row["evidence_id"],
                "fact_type": fact_type,
                "node_id": row.get("node_id"),
                "edge_id": row.get("edge_id"),
                "fact_status": fact_status,
                "source_document_id": row.get("source_document_id"),
                "source_document_title_hash": sha256_text(row.get("source_document_title")),
                "source_document_category": row.get("source_document_category"),
                "source_document_language": state["language"],
                "source_document_approval_status": row.get("source_document_approval_status"),
                "source_document_lifecycle_status": row.get("document_lifecycle_status"),
                "source_document_parse_status": row.get("document_parse_status"),
                "source_document_approval_mode": state["approval_mode"],
                "source_document_version": state["version"],
                "source_document_current_flag": state["current"],
                "source_document_superseded_by": state["superseded_by"],
                "source_chunk_id": row.get("source_chunk_id"),
                "source_semantic_unit_id": row.get("semantic_unit_id"),
                "source_locator": _source_locator(row),
                "extraction_run_id": row.get("extraction_run_id"),
                "candidate_id": row.get("candidate_id"),
                "conversion_record_id": row.get("conversion_record_id"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("created_at"),
                "production_context_usage": {
                    "current_implementation": runtime_usage,
                    "fact_active": fact_status == "active",
                    "source_valid_for_production": not any(
                        state[key]
                        for key in (
                            "pending",
                            "archived",
                            "superseded",
                            "marketing",
                            "english",
                            "approval_invalid",
                        )
                    ),
                },
                "rag_context_usage": {"persisted_record_count": qa_usage, **runtime_usage},
                "diagnosis_usage": {
                    "persisted_record_count": diagnosis_usage,
                    "shares_business_context_service": True,
                    "runtime_context_returned": runtime_usage.get("returned", False),
                },
                "actual_state_flags": {
                    "pending": state["pending"],
                    "archived": state["archived"],
                    "superseded": state["superseded"],
                    "marketing": state["marketing"],
                    "english": state["english"],
                    "approval_invalid": state["approval_invalid"],
                },
                "other_current_valid_evidence_count": valid_current_evidence_count,
                "preliminary_classification": _preliminary_classification(
                    {**row, "state": state}, valid_current_evidence_count
                ),
            }
            output.append(item)

    state_counts = Counter()
    classification_counts = Counter()
    for item in output:
        classification_counts[item["preliminary_classification"]] += 1
        for key, enabled in item["actual_state_flags"].items():
            if enabled:
                state_counts[key] += 1
    summary = {
        "version": "task25g_r1_archived_evidence_forensics_v1",
        "generated_at": now_iso(),
        "status": "PASS" if len(output) == 12 else "FAIL",
        "evidence_count": len(output),
        "distinct_document_count": len({item["source_document_id"] for item in output}),
        "distinct_fact_count": len({item["node_id"] or item["edge_id"] for item in output}),
        "actual_state_counts": dict(sorted(state_counts.items())),
        "preliminary_classification_counts": dict(sorted(classification_counts.items())),
        "runtime_context_returned_count": sum(
            bool(item["production_context_usage"]["current_implementation"].get("returned")) for item in output
        ),
        "title_values_recorded": False,
        "evidence_text_recorded": False,
        "findings": [
            "Task 25G pending and marketing counts were not independently classified.",
            "Archived, language, approval, category, and superseded state are reported independently here.",
        ],
    }
    write_json("archived_evidence_forensics.json", output)
    write_csv("archived_evidence_forensics.csv", output, CSV_FIELDS)
    write_json("archived_evidence_summary.json", summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "evidence_count": summary["evidence_count"],
                "distinct_fact_count": summary["distinct_fact_count"],
                "actual_state_counts": summary["actual_state_counts"],
                "classifications": summary["preliminary_classification_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
