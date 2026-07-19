from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from task25g_r1_common import (
    BACKEND,
    EXPECTED_ALEMBIC_REVISION,
    ROOT,
    RUNTIME,
    TASK25G_REPORT,
    TASK25G_RUNTIME,
    alembic_state,
    directory_manifest,
    git_snapshot,
    now_iso,
    public_path,
    read_json,
    sha256_file,
    sha256_value,
    table_exists,
    write_json,
    zip_inventory,
)


OUTPUTS = (
    RUNTIME / "task25g_snapshot.json",
    RUNTIME / "hash_manifest.json",
    RUNTIME / "leakage_baseline.json",
)


def _load_task25g_scope() -> dict[str, Any]:
    path = TASK25G_RUNTIME / "kg_scope_and_evidence.json"
    if not path.is_file():
        raise RuntimeError("Task 25G scope evidence is missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Task 25G scope evidence is invalid")
    return value


def _leakage_ids(scope: dict[str, Any]) -> list[str]:
    result = []
    for issue in scope.get("issues") or []:
        evidence_id = str(issue.get("evidence_id") or "").strip()
        if evidence_id and evidence_id not in result:
            result.append(evidence_id)
    if len(result) != 12:
        raise RuntimeError(f"expected 12 frozen leakage evidence IDs, found {len(result)}")
    return result


def _database_baseline(evidence_ids: list[str]) -> dict[str, Any]:
    from app.core.database import SessionLocal

    statement = text(
        """
        SELECT ev.id::text AS evidence_id,
               ev.node_id::text AS node_id,
               ev.edge_id::text AS edge_id,
               ev.document_id::text AS document_id,
               ev.chunk_id::text AS chunk_id,
               ev.source_type,
               ev.source_id::text AS source_id,
               d.review_status AS document_review_status,
               d.status AS document_lifecycle_status,
               d.parse_status AS document_parse_status,
               d.document_type AS document_category,
               d.metadata_json AS document_metadata,
               c.metadata_json AS chunk_metadata
        FROM kg_evidence_links ev
        LEFT JOIN knowledge_documents d ON d.id=ev.document_id
        LEFT JOIN knowledge_chunks c ON c.id=ev.chunk_id
        WHERE ev.id::text IN :evidence_ids
        ORDER BY ev.id::text
        """
    ).bindparams(bindparam("evidence_ids", expanding=True))

    with SessionLocal() as session:
        rows = [dict(row) for row in session.execute(statement, {"evidence_ids": evidence_ids}).mappings()]
        if len(rows) != len(evidence_ids):
            found = {row["evidence_id"] for row in rows}
            missing = sorted(set(evidence_ids) - found)
            raise RuntimeError(f"frozen leakage evidence missing from database: {missing}")

        vector_namespaces: list[dict[str, Any]] = []
        if table_exists(session, "knowledge_chunk_vector_indexes"):
            vector_namespaces = [
                {"namespace": str(row[0]), "count": int(row[1])}
                for row in session.execute(
                    text(
                        """
                        SELECT namespace, count(*)
                        FROM knowledge_chunk_vector_indexes
                        GROUP BY namespace
                        ORDER BY namespace
                        """
                    )
                )
            ]

    sanitized = []
    for row in rows:
        document_metadata = row.pop("document_metadata") or {}
        chunk_metadata = row.pop("chunk_metadata") or {}
        sanitized.append(
            {
                **row,
                "source_semantic_unit_id": chunk_metadata.get("semantic_unit_id"),
                "document_language": document_metadata.get("normalized_language"),
                "document_version": document_metadata.get("version"),
                "document_current_flag": bool(document_metadata.get("current_version", True)),
                "document_superseded_by": document_metadata.get("superseded_by_document_id"),
                "document_approval_mode": document_metadata.get("approval_mode"),
            }
        )
    return {"leakage_evidence": sanitized, "vector_namespaces": vector_namespaces}


def _source_manifest() -> dict[str, Any]:
    required_files = [
        TASK25G_REPORT,
        TASK25G_RUNTIME / "kg_inventory.json",
        TASK25G_RUNTIME / "kg_integrity.json",
        TASK25G_RUNTIME / "kg_scope_and_evidence.json",
        TASK25G_RUNTIME / "kg_extraction_lineage.json",
        TASK25G_RUNTIME / "kg_rag_integration.json",
        TASK25G_RUNTIME / "kg_query_performance.json",
    ]
    missing = [public_path(path) for path in required_files if not path.is_file()]
    if missing:
        raise RuntimeError(f"Task 25G frozen input missing: {missing}")
    return {
        "report": {
            "path": public_path(TASK25G_REPORT),
            "size": TASK25G_REPORT.stat().st_size,
            "sha256": sha256_file(TASK25G_REPORT),
        },
        "runtime": directory_manifest(TASK25G_RUNTIME),
        "required_files": [
            {
                "path": public_path(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in required_files
        ],
    }


def main() -> int:
    if any(path.exists() for path in OUTPUTS):
        raise SystemExit("Task 25G-R1 snapshot already exists; refusing to overwrite")

    scope = _load_task25g_scope()
    evidence_ids = _leakage_ids(scope)
    database = _database_baseline(evidence_ids)
    source_manifest = _source_manifest()
    alembic = alembic_state()
    env_path = BACKEND / ".env"
    env_hash = {
        "path": public_path(env_path),
        "exists": env_path.is_file(),
        "sha256": sha256_file(env_path),
        "values_recorded": False,
    }

    leakage = {
        "version": "task25g_r1_leakage_baseline_v1",
        "created_at": now_iso(),
        "source": public_path(TASK25G_RUNTIME / "kg_scope_and_evidence.json"),
        "source_sha256": sha256_file(TASK25G_RUNTIME / "kg_scope_and_evidence.json"),
        "original_task25g_status": scope.get("status"),
        "original_reported_counts": {
            "scope_leakage": scope.get("scope_leakage_count"),
            "pending_leakage": scope.get("pending_leakage"),
            "marketing_leakage": scope.get("marketing_leakage"),
            "english_leakage": scope.get("english_leakage"),
        },
        "evidence_count": len(evidence_ids),
        "evidence_ids": evidence_ids,
        "facts": database["leakage_evidence"],
        "classification_status": "ORIGINAL_TASK25G_CLASSIFICATION_FROZEN_UNVERIFIED",
    }
    leakage["baseline_sha256"] = sha256_value(leakage)

    hash_manifest = {
        "version": "task25g_r1_hash_manifest_v1",
        "created_at": now_iso(),
        "task25g": source_manifest,
        "backend_env": env_hash,
        "leakage_baseline_sha256": leakage["baseline_sha256"],
    }
    hash_manifest["manifest_sha256"] = sha256_value(hash_manifest)

    snapshot = {
        "version": "task25g_r1_snapshot_v1",
        "created_at": now_iso(),
        "task25g_status": "TASK25G_KG_GROUNDING_GATE_FAILED",
        "alembic": alembic,
        "expected_alembic_revision": EXPECTED_ALEMBIC_REVISION,
        "database": {
            "status": "AVAILABLE",
            "leakage_evidence_count": len(database["leakage_evidence"]),
            "vector_namespaces": database["vector_namespaces"],
        },
        "git": git_snapshot(),
        "zip_inventory": zip_inventory(),
        "task25g_hash_manifest_sha256": hash_manifest["manifest_sha256"],
        "boundaries": {
            "task25g_runtime_writes": 0,
            "task25g_report_writes": 0,
            "database_writes": 0,
            "knowledge_content_writes": 0,
            "embedding_calls": 0,
            "vector_writes": 0,
            "full_reindex": False,
            "package_generated": False,
            "git_mutation": False,
            "expert_auto_write": False,
            "real_machine_acceptance_executed": False,
        },
    }

    RUNTIME.mkdir(parents=True, exist_ok=True)
    write_json("leakage_baseline.json", leakage, overwrite=False)
    write_json("hash_manifest.json", hash_manifest, overwrite=False)
    write_json("task25g_snapshot.json", snapshot, overwrite=False)
    print(
        json.dumps(
            {
                "status": "TASK25G_R1_SNAPSHOT_FROZEN",
                "leakage_evidence_count": len(evidence_ids),
                "alembic_current": alembic["current"],
                "task25g_runtime_sha256": source_manifest["runtime"]["aggregate_sha256"],
                "staged_files": len(snapshot["git"]["staged_files"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
