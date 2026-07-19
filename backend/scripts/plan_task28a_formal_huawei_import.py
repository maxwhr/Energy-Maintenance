"""Build a read-only, approval-gated formal Huawei corpus import plan.

Task 28A-R3A deliberately never applies the plan.  The formal database is
opened only inside ``BEGIN TRANSACTION READ ONLY`` and this program contains
no data-definition or data-modification operation.  A later, separately
authorized task must create a fresh backup and consume the frozen plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from import_competition_knowledge_corpus import (  # noqa: E402
    FORMAL_GATE_CONTRACT_VERSION,
    QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS,
    _assert_formal_gates,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "task28a-r3"
R3A_R1_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "task28a-r3-r1"
R3A_R2_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "task28a-r3-r2"
DOCS_ROOT = PROJECT_ROOT / "docs" / "project_audit"
MANIFEST_PATH = (
    PROJECT_ROOT
    / "knowledge_assets"
    / "competition_corpus_v1"
    / "manifests"
    / "knowledge_import_manifest.json"
)
RAW_ROOT = PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1" / "raw"
TEST_ENV_PATH = PROJECT_ROOT / ".env.task27a.test.local"
FORMAL_ENV_PATH = BACKEND_ROOT / ".env"
EXPECTED_TEST = {
    "host": "127.0.0.1",
    "port": 55433,
    "database": "energy_maintenance_task27a_test",
    "username": "energy_maintenance_test_user",
}
EXPECTED_FORMAL = {
    "host": "127.0.0.1",
    "port": 55432,
    "database": "energy_maintenance",
    "username": "energy_user",
}
EXPECTED_ALEMBIC_HEAD = "20260712_0015"
EXPECTED_V2_PLAN_SHA256 = "200d21ed461ebd9c22d8adbb966b1504ff6ec8714efa4005ef6d0c772bfa0a20"
EXPECTED_PRE_REPAIR_IMPORTER_SHA256 = "c0ecf629a290ac95ae22ca7490ba35e00f9f089953453c24570252e3e32253dc"
HUAWEI_SCOPE = "huawei_sun2000_competition_v1"
PROTECTED_QA_ID = "4a9eeab8-91de-43bb-90ec-78a3d6bba7be"
PROTECTED_QA_TRACE_ID = "qa_req_a92bd4d743373941ff949e900b972057"
PROTECTED_QA_REQUEST_ID = "req_075409308b6f40c989324d382a3bb574"
LOGICAL_TABLES = {
    "knowledge_documents": "knowledge_documents",
    "knowledge_chunks": "knowledge_chunks",
    "knowledge_contributions": "knowledge_contributions",
    "qa_records": "qa_records",
    "diagnosis_records": "diagnosis_records",
    "maintenance_tasks": "maintenance_tasks",
    "devices": "devices",
    "media": "uploaded_media",
    "multimodal_cases": "multimodal_maintenance_cases",
    "correction_records": "model_output_corrections",
    "kg_nodes": "kg_nodes",
    "kg_edges": "kg_edges",
    "sop_templates": "sop_templates",
    "sop_executions": "sop_execution_records",
    "users": "users",
}


class PreflightError(RuntimeError):
    """Raised for a failed no-write preflight guard."""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any, *, indent: int | None = None) -> bytes:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        separators=None if indent is not None else (",", ":"),
        default=str,
    )
    return (rendered + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value, indent=2))


def safe_scalar(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise PreflightError(f"required environment file is missing: {path.name}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_formal_database_url() -> str:
    """Prefer an ephemeral Task 28A preflight override over the developer .env."""

    return os.getenv("TASK28A_FORMAL_DATABASE_URL", "").strip() or read_dotenv(FORMAL_ENV_PATH).get(
        "DATABASE_URL", ""
    )


def sanitize_url(url: URL) -> dict[str, Any]:
    return {
        "host": url.host,
        "port": url.port,
        "database": url.database,
        "username": url.username,
        "password_present": bool(url.password),
    }


def assert_identity(url: URL, expected: dict[str, Any], label: str) -> list[str]:
    actual = sanitize_url(url)
    return [
        field
        for field in ("host", "port", "database", "username")
        if actual.get(field) != expected[field]
    ]


def psycopg_conninfo(url: URL) -> str:
    if not url.host or not url.database or not url.username or url.password is None:
        raise PreflightError("DATABASE_URL is incomplete")
    return (
        f"host={quote(url.host, safe='')} port={int(url.port or 5432)} "
        f"dbname={quote(url.database, safe='')} user={quote(url.username, safe='')} "
        f"password={quote(url.password, safe='')} connect_timeout=8"
    )


def normalize_text(value: str | None) -> str:
    return (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def digest_text(value: str | None) -> str:
    return sha256_bytes(normalize_text(value).encode("utf-8"))


def normalize_title(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def metadata_digest(value: Any) -> str:
    metadata = dict(value or {})
    for key in ("file_path", "absolute_path", "raw_path", "upload_path"):
        metadata.pop(key, None)
    return sha256_bytes(canonical_json(metadata))


def metadata_source_sha(metadata: Any, source: str | None) -> str | None:
    metadata = metadata or {}
    value = metadata.get("task28a_source_sha256") or metadata.get("source_sha256")
    if value:
        return str(value)
    prefix = "task28a_sha256:"
    if source and source.startswith(prefix):
        return source[len(prefix) :]
    return None


def metadata_scope(metadata: Any) -> str | None:
    return (metadata or {}).get("scope")


def metadata_model(metadata: Any, product_series: str | None) -> str | None:
    metadata = metadata or {}
    return metadata.get("model") or metadata.get("model_name") or product_series


def path_under(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def protected_hash_manifest() -> dict[str, Any]:
    targets = (
        PROJECT_ROOT / "backend" / "app",
        PROJECT_ROOT / "frontend" / "src",
        PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1" / "manifests",
        RAW_ROOT,
        BACKEND_ROOT / "scripts" / "import_competition_knowledge_corpus.py",
    )
    entries: list[dict[str, Any]] = []
    for target in targets:
        if target.is_file():
            paths = [target]
        elif target.is_dir():
            paths = sorted(path for path in target.rglob("*") if path.is_file())
        else:
            paths = []
        for path in paths:
            entries.append(
                {
                    "path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    aggregate = sha256_bytes(canonical_json(entries))
    return {"algorithm": "sha256", "file_count": len(entries), "aggregate_sha256": aggregate, "files": entries}


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise PreflightError("knowledge import manifest is missing")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def is_huawei_candidate(item: dict[str, Any]) -> bool:
    return (
        item.get("manufacturer_normalized") == "huawei"
        and item.get("scope") == HUAWEI_SCOPE
        and item.get("selected_for_test_import") is True
        and item.get("is_formal_retrieval_candidate") is True
        and item.get("source_type") != "derived_text_alias"
    )


def raw_source_for(item: dict[str, Any]) -> Path:
    source = Path(str(item.get("raw_path") or ""))
    if not source.is_absolute():
        source = RAW_ROOT / str(item.get("relative_path") or "")
    if not path_under(RAW_ROOT, source):
        raise PreflightError("manifest source resolves outside the controlled raw corpus")
    return source


def build_exclusions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    exclusions: list[dict[str, Any]] = []
    for item in manifest.get("documents", []):
        if is_huawei_candidate(item):
            continue
        manufacturer = item.get("manufacturer_normalized")
        source_type = item.get("source_type")
        scope = item.get("scope")
        if manufacturer == "sungrow":
            reason = "future_sungrow_scope_not_authorized_for_huawei_formal_import"
            exclusions.append(
                {
                    "kind": "knowledge_document",
                    "relative_path": item.get("relative_path"),
                    "source_sha256": item.get("sha256"),
                    "reason": reason,
                    "formal_import_candidate": False,
                    "retrieval_eligible": False,
                    "target_scope": None,
                }
            )
        elif source_type == "derived_text_alias":
            exclusions.append(
                {
                    "kind": "knowledge_document",
                    "relative_path": item.get("relative_path"),
                    "source_sha256": item.get("sha256"),
                    "reason": "derived_text_alias_not_a_formal_source_document",
                    "formal_import_candidate": False,
                    "retrieval_eligible": False,
                    "target_scope": None,
                }
            )
        else:
            exclusions.append(
                {
                    "kind": "knowledge_document",
                    "relative_path": item.get("relative_path"),
                    "source_sha256": item.get("sha256"),
                    "reason": "not_in_approved_huawei_candidate_set",
                    "formal_import_candidate": False,
                    "retrieval_eligible": False,
                    "target_scope": None,
                }
            )
    for asset in manifest.get("media_assets", []):
        exclusions.append(
            {
                "kind": "media_asset",
                "relative_path": asset.get("relative_path"),
                "source_sha256": asset.get("sha256"),
                "reason": "multimodal_media_is_not_included_in_formal_knowledge_document_import",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            }
        )
    for item in manifest.get("excluded_assets", []):
        exclusions.append(
            {
                "kind": "excluded_asset",
                "relative_path": item.get("relative_path"),
                "source_sha256": item.get("sha256"),
                "reason": item.get("reason") or "excluded_by_corpus_manifest",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            }
        )
    exclusions.extend(
        [
            {
                "kind": "fault_case_annotation",
                "relative_path": "annotations/fault_case_01.json",
                "reason": "multimodal_test_case_not_in_formal_knowledge_document_import",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
            {
                "kind": "fault_case_annotation",
                "relative_path": "annotations/fault_case_02.json",
                "reason": "multimodal_test_case_not_in_formal_knowledge_document_import",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
            {
                "kind": "qa_records",
                "relative_path": None,
                "reason": "test_qa_records_are_evidence_only_and_never_imported_as_knowledge_documents",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
            {
                "kind": "multimodal_test_data",
                "relative_path": None,
                "reason": "multimodal_case_evidence_and_fault_case_results_are_not_in_this_document_import_scope",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
            {
                "kind": "trace_records",
                "relative_path": None,
                "reason": "request_trace_and_audit_records_are_never_imported_as_knowledge_documents",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
            {
                "kind": "review_records",
                "relative_path": None,
                "reason": "test_review_records_are_provenance_evidence_not_import_payloads",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
            {
                "kind": "fixtures_and_archived_records",
                "relative_path": None,
                "reason": "fixtures_pending_review_and_archived_records_are_excluded_from_formal_import",
                "formal_import_candidate": False,
                "retrieval_eligible": False,
                "target_scope": None,
            },
        ]
    )
    return exclusions


def connect_read_only(url: URL) -> psycopg.Connection[Any]:
    connection = psycopg.connect(psycopg_conninfo(url), autocommit=False)
    cursor = connection.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION READ ONLY")
        cursor.execute("SHOW transaction_read_only")
        if str(cursor.fetchone()[0]).lower() != "on":
            raise PreflightError("database did not confirm transaction_read_only=on")
    finally:
        cursor.close()
    return connection


def connect_formal_readonly_with_probe(url: URL) -> tuple[psycopg.Connection[Any], dict[str, Any]]:
    """Open a constrained formal session and prove business writes are refused.

    The only attempted write is ``CREATE TEMP TABLE`` inside an explicit
    read-only transaction. PostgreSQL must reject it; the transaction is then
    rolled back before any baseline query is issued.
    """

    connection = psycopg.connect(psycopg_conninfo(url), autocommit=True)
    evidence = {
        "default_transaction_read_only_set": False,
        "statement_timeout": "30s",
        "lock_timeout": "5s",
        "idle_in_transaction_session_timeout": "60s",
        "transaction_read_only_verified": False,
        "readonly_write_probe_rejected": False,
        "readonly_write_probe_error_type": None,
    }
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = on")
        cursor.execute("SET statement_timeout = '30s'")
        cursor.execute("SET lock_timeout = '5s'")
        cursor.execute("SET idle_in_transaction_session_timeout = '60s'")
        evidence["default_transaction_read_only_set"] = True
        cursor.execute("BEGIN TRANSACTION READ ONLY")
        cursor.execute("SHOW transaction_read_only")
        evidence["transaction_read_only_verified"] = str(cursor.fetchone()[0]).lower() == "on"
        if not evidence["transaction_read_only_verified"]:
            cursor.execute("ROLLBACK")
            connection.close()
            raise PreflightError("formal transaction_read_only was not enabled")
        try:
            cursor.execute("CREATE TEMP TABLE task28a_readonly_probe(id integer)")
        except Exception as exc:  # PostgreSQL must reject DDL in a read-only transaction.
            evidence["readonly_write_probe_rejected"] = True
            evidence["readonly_write_probe_error_type"] = type(exc).__name__
        finally:
            cursor.execute("ROLLBACK")
        if not evidence["readonly_write_probe_rejected"]:
            connection.close()
            raise PreflightError("SECURITY_BOUNDARY_VIOLATION_READONLY_NOT_ENFORCED")
        cursor.execute("BEGIN TRANSACTION READ ONLY")
        cursor.execute("SHOW transaction_read_only")
        if str(cursor.fetchone()[0]).lower() != "on":
            cursor.execute("ROLLBACK")
            connection.close()
            raise PreflightError("formal read-only transaction was not restored after the probe")
    return connection, evidence


def fetch_all(connection: psycopg.Connection[Any], query: str, parameters: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(query, tuple(parameters))
        columns = [description.name for description in cursor.description or ()]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def fetch_one(connection: psycopg.Connection[Any], query: str, parameters: Iterable[Any] = ()) -> dict[str, Any] | None:
    rows = fetch_all(connection, query, parameters)
    return rows[0] if rows else None


def table_count(connection: psycopg.Connection[Any], table_name: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {} ").format(sql.Identifier(table_name)))
        return int(cursor.fetchone()[0])


def table_columns(connection: psycopg.Connection[Any], table_name: str) -> set[str]:
    return {
        row["column_name"]
        for row in fetch_all(
            connection,
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
    }


def verify_test_candidates(url: URL, manifest: dict[str, Any]) -> dict[str, Any]:
    identity_mismatch = assert_identity(url, EXPECTED_TEST, "test")
    if identity_mismatch:
        raise PreflightError(f"test database identity mismatch: {', '.join(identity_mismatch)}")

    candidates = [item for item in manifest.get("documents", []) if is_huawei_candidate(item)]
    findings: list[dict[str, Any]] = []
    with connect_read_only(url) as connection:
        try:
            version = fetch_one(connection, "SELECT version_num FROM alembic_version")
            if not version or version["version_num"] != EXPECTED_ALEMBIC_HEAD:
                raise PreflightError("test database Alembic revision is not the expected Task 28A head")
            documents = fetch_all(
                connection,
                """
                SELECT id, title, manufacturer, product_series, document_type, source, file_name,
                       file_size, parse_status, chunk_count, metadata_json, review_status,
                       status, reviewed_by, reviewed_at, error_message, created_at, updated_at
                FROM knowledge_documents
                """,
            )
            document_by_sha: dict[str, list[dict[str, Any]]] = {}
            for document in documents:
                document_by_sha.setdefault(
                    metadata_source_sha(document.get("metadata_json"), document.get("source")) or "", []
                ).append(document)

            for item in candidates:
                errors: list[str] = []
                source_path = raw_source_for(item)
                source_exists = source_path.is_file()
                actual_source_sha = file_sha256(source_path) if source_exists else None
                if not source_exists:
                    errors.append("source_file_missing")
                elif actual_source_sha != item.get("sha256"):
                    errors.append("source_sha256_mismatch")
                elif source_path.stat().st_size != int(item.get("size_bytes") or 0):
                    errors.append("source_file_size_mismatch")
                matches = document_by_sha.get(str(item.get("sha256")), [])
                if len(matches) != 1:
                    errors.append("test_document_missing_or_duplicate")
                    document = None
                else:
                    document = matches[0]
                chunk_rows: list[dict[str, Any]] = []
                if document is not None:
                    chunk_rows = fetch_all(
                        connection,
                        """
                        SELECT id, chunk_index, content, content_hash, page_number, section_title,
                               char_count, status, metadata_json, created_at
                        FROM knowledge_chunks
                        WHERE document_id = %s
                        ORDER BY chunk_index ASC, id ASC
                        """,
                        (document["id"],),
                    )
                    metadata = document.get("metadata_json") or {}
                    if document.get("manufacturer") != "huawei":
                        errors.append("manufacturer_not_huawei")
                    if document.get("review_status") != "approved":
                        errors.append("review_not_approved")
                    if document.get("parse_status") != "parsed":
                        errors.append("parse_not_parsed")
                    if int(document.get("chunk_count") or 0) <= 0:
                        errors.append("chunk_count_not_positive")
                    if int(document.get("chunk_count") or 0) != len(chunk_rows):
                        errors.append("chunk_count_does_not_match_rows")
                    if metadata_scope(metadata) != HUAWEI_SCOPE:
                        errors.append("scope_mismatch")
                    if metadata.get("is_formal_retrieval_candidate") is not True:
                        errors.append("manifest_retrieval_flag_missing")
                    if metadata.get("task28a_corpus_id") != "competition_corpus_v1":
                        errors.append("corpus_id_mismatch")
                    if document.get("error_message"):
                        errors.append("document_has_parse_error")
                    if int(document.get("file_size") or 0) != int(item.get("size_bytes") or 0):
                        errors.append("stored_file_size_mismatch")
                    if not document.get("reviewed_at") or not document.get("reviewed_by"):
                        errors.append("review_provenance_missing")
                    indices = [int(row["chunk_index"]) for row in chunk_rows]
                    if len(indices) != len(set(indices)):
                        errors.append("duplicate_chunk_index")
                    if indices and indices != list(range(indices[0], indices[0] + len(indices))):
                        errors.append("non_contiguous_chunk_index")
                    if any(not normalize_text(str(row.get("content") or "")) for row in chunk_rows):
                        errors.append("empty_chunk_content")
                    if any(row.get("content_hash") and row["content_hash"] != digest_text(row.get("content")) for row in chunk_rows):
                        errors.append("chunk_content_hash_mismatch")
                chunk_hashes = [digest_text(row.get("content")) for row in chunk_rows]
                ordered_chunk_digest = sha256_bytes("".join(chunk_hashes).encode("ascii"))
                metadata = (document or {}).get("metadata_json") or {}
                findings.append(
                    {
                        "id": str(document["id"]) if document else None,
                        "title": document.get("title") if document else item.get("title"),
                        "source_relative_path": item.get("relative_path"),
                        "source_sha256": item.get("sha256"),
                        "source_file_exists": source_exists,
                        "source_file_size_matches_manifest": source_exists
                        and source_path.stat().st_size == int(item.get("size_bytes") or 0),
                        "source_sha256_verified": actual_source_sha == item.get("sha256"),
                        "file_size": int((document or {}).get("file_size") or item.get("size_bytes") or 0),
                        "document_type": (document or {}).get("document_type") or item.get("document_type"),
                        "manufacturer": (document or {}).get("manufacturer") or item.get("manufacturer_normalized"),
                        "product_series": (document or {}).get("product_series") or item.get("product_family"),
                        "model": metadata_model(metadata, (document or {}).get("product_series")),
                        "document_version": metadata.get("document_version") or item.get("detected_document_version"),
                        "language": metadata.get("language") or item.get("language"),
                        "scope": metadata_scope(metadata),
                        "review_status": (document or {}).get("review_status"),
                        "parse_status": (document or {}).get("parse_status"),
                        "chunk_count": len(chunk_rows),
                        "ordered_chunk_digest": ordered_chunk_digest,
                        "metadata_digest": metadata_digest(metadata),
                        "validation_errors": errors,
                    }
                )
        finally:
            connection.rollback()

    valid = [item for item in findings if not item["validation_errors"]]
    return {
        "identity": sanitize_url(url),
        "alembic_current": EXPECTED_ALEMBIC_HEAD,
        "candidate_count": len(findings),
        "valid_candidate_count": len(valid),
        "candidates": findings,
        "status": "PASSED" if len(findings) == 10 and len(valid) == 10 else "FAILED",
    }


def formal_baseline(url: URL, *, verify_readonly_probe: bool = False) -> dict[str, Any]:
    identity_mismatch = assert_identity(url, EXPECTED_FORMAL, "formal")
    if identity_mismatch:
        return {
            "status": "BLOCKED_FORMAL_DATABASE_IDENTITY_MISMATCH",
            "identity": sanitize_url(url),
            "expected": EXPECTED_FORMAL,
            "mismatched_fields": identity_mismatch,
            "formal_writes": 0,
        }
    try:
        readonly_evidence: dict[str, Any] = {
            "transaction_read_only_verified": True,
            "readonly_write_probe_rejected": "not_executed",
        }
        if verify_readonly_probe:
            connection, readonly_evidence = connect_formal_readonly_with_probe(url)
        else:
            connection = connect_read_only(url)
    except Exception as exc:  # noqa: BLE001 - report a sanitized failure only.
        return {
            "status": "BLOCKED_FORMAL_DATABASE_UNREACHABLE",
            "identity": sanitize_url(url),
            "error_type": type(exc).__name__,
            "error_message": str(exc).split("password=")[0][:300],
            "formal_writes": 0,
        }

    try:
        database_identity = fetch_one(
            connection,
            """
            SELECT current_database() AS database, current_user AS username,
                   host(inet_server_addr()) AS server_address, inet_server_port() AS server_port,
                   current_setting('transaction_read_only') AS transaction_read_only
            """,
        ) or {}
        role = fetch_one(
            connection,
            "SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user",
        ) or {}
        version = fetch_one(connection, "SELECT version_num FROM alembic_version") or {}
        actual_tables = {
            row["table_name"]
            for row in fetch_all(
                connection,
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """,
            )
        }
        from app.core.database import Base
        from app.models import __all__ as _loaded_models  # noqa: F401

        metadata_tables = set(Base.metadata.tables)
        counts: dict[str, Any] = {}
        for logical_name, physical_name in LOGICAL_TABLES.items():
            counts[logical_name] = (
                table_count(connection, physical_name)
                if physical_name in actual_tables
                else "not_applicable"
            )
        document_rows = (
            fetch_all(
                connection,
                """
                SELECT id, title, manufacturer, product_series, document_type, source, file_name,
                       parse_status, chunk_count, metadata_json, review_status, status,
                       created_at, updated_at
                FROM knowledge_documents
                """,
            )
            if "knowledge_documents" in actual_tables
            else []
        )
        documents_by_sha: dict[str, list[dict[str, Any]]] = {}
        documents_by_title: dict[str, list[dict[str, Any]]] = {}
        for document in document_rows:
            source_sha = metadata_source_sha(document.get("metadata_json"), document.get("source"))
            if source_sha:
                documents_by_sha.setdefault(source_sha, []).append(document)
            documents_by_title.setdefault(normalize_title(document.get("title")), []).append(document)
        qa_summary: dict[str, Any]
        if "qa_records" not in actual_tables:
            qa_summary = {"exists": False, "reason": "qa_records_not_present"}
        else:
            qa_columns = table_columns(connection, "qa_records")
            protected_fields = ["id", "question", "trace_id", "created_at", "updated_at"]
            if "request_id" in qa_columns:
                protected_fields.append("request_id")
            if "status" in qa_columns:
                protected_fields.append("status")
            qa_row = fetch_one(
                connection,
                f"SELECT {', '.join(protected_fields)} FROM qa_records WHERE id = %s AND trace_id = %s",
                (PROTECTED_QA_ID, PROTECTED_QA_TRACE_ID),
            )
            request_id_matches = (
                qa_row.get("request_id") == PROTECTED_QA_REQUEST_ID
                if qa_row is not None and "request_id" in qa_columns
                else None
            )
            qa_summary = {
                "exists": qa_row is not None,
                "id": PROTECTED_QA_ID,
                "trace_id": PROTECTED_QA_TRACE_ID,
                "request_id": PROTECTED_QA_REQUEST_ID,
                "request_id_column_present": "request_id" in qa_columns,
                "request_id_matches": request_id_matches,
                "request_id_verification": (
                    "matched_qa_record"
                    if request_id_matches is True
                    else "mismatched_qa_record"
                    if request_id_matches is False
                    else "not_persisted_in_qa_records"
                ),
                "status_column_present": "status" in qa_columns,
                "status": qa_row.get("status") if qa_row and "status" in qa_row else "not_applicable",
                "created_at": safe_scalar(qa_row.get("created_at")) if qa_row else None,
                "updated_at": safe_scalar(qa_row.get("updated_at")) if qa_row else None,
                "summary_row_sha256": sha256_bytes(
                    canonical_json(
                        {
                            "id": str(qa_row.get("id")) if qa_row else None,
                            "question_digest": digest_text(qa_row.get("question")) if qa_row else None,
                            "trace_id": qa_row.get("trace_id") if qa_row else None,
                            "updated_at": safe_scalar(qa_row.get("updated_at")) if qa_row else None,
                        }
                    )
                )
                if qa_row
                else None,
            }

        document_stats = {
            "total": len(document_rows),
            "manufacturer": dict(Counter((row.get("manufacturer") or "unknown") for row in document_rows)),
            "review_status": dict(Counter((row.get("review_status") or "unknown") for row in document_rows)),
            "parse_status": dict(Counter((row.get("parse_status") or "unknown") for row in document_rows)),
            "document_type": dict(Counter((row.get("document_type") or "unknown") for row in document_rows)),
            "scope": dict(Counter((metadata_scope(row.get("metadata_json")) or "unknown") for row in document_rows)),
            "status": dict(Counter((row.get("status") or "unknown") for row in document_rows)),
            "blank_source_sha256": sum(
                metadata_source_sha(row.get("metadata_json"), row.get("source")) is None for row in document_rows
            ),
        }
        formal_huawei_rows = [
            row
            for row in document_rows
            if (row.get("manufacturer") or "").casefold() in {"huawei", "华为"}
            and row.get("product_series") in {"SUN2000", "FusionSolar"}
            and metadata_scope(row.get("metadata_json")) == HUAWEI_SCOPE
        ]
        huawei_document_ids = [str(row["id"]) for row in formal_huawei_rows]
        huawei_chunk_count = 0
        if huawei_document_ids and "knowledge_chunks" in actual_tables:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ANY(%s::uuid[])",
                    (huawei_document_ids,),
                )
                huawei_chunk_count = int(cursor.fetchone()[0])
        huawei_scope_summary = [
            {
                "id": str(row["id"]),
                "title": row.get("title"),
                "source_sha256": metadata_source_sha(row.get("metadata_json"), row.get("source")),
                "manufacturer": row.get("manufacturer"),
                "product_series": row.get("product_series"),
                "model": metadata_model(row.get("metadata_json"), row.get("product_series")),
                "scope": metadata_scope(row.get("metadata_json")),
                "review_status": row.get("review_status"),
                "parse_status": row.get("parse_status"),
                "chunk_count": int(row.get("chunk_count") or 0),
                "status": row.get("status"),
            }
            for row in formal_huawei_rows
        ]
        schema_missing_tables = sorted(metadata_tables - actual_tables)
        schema_matches = not schema_missing_tables
        protected_qa_matches = (
            qa_summary.get("exists") is True
            and qa_summary.get("trace_id") == PROTECTED_QA_TRACE_ID
            and qa_summary.get("request_id_matches") is not False
        )
        return {
            "status": "PASSED"
            if database_identity.get("database") == EXPECTED_FORMAL["database"]
            and database_identity.get("username") == EXPECTED_FORMAL["username"]
            and database_identity.get("server_address") == EXPECTED_FORMAL["host"]
            and database_identity.get("server_port") == EXPECTED_FORMAL["port"]
            and database_identity.get("transaction_read_only") == "on"
            and role.get("rolsuper") is False
            and version.get("version_num") == EXPECTED_ALEMBIC_HEAD
            and schema_matches
            and protected_qa_matches
            else "BLOCKED_FORMAL_DATABASE_IDENTITY_OR_SCHEMA_MISMATCH",
            "identity": sanitize_url(url),
            "database_identity": database_identity,
            "role": role,
            "alembic_current": version.get("version_num"),
            "alembic_expected": EXPECTED_ALEMBIC_HEAD,
            "transaction_read_only_verified": database_identity.get("transaction_read_only") == "on",
            "readonly_session_evidence": readonly_evidence,
            "formal_writes": 0,
            "metadata_table_comparison": {
                "model_metadata_tables": sorted(metadata_tables),
                "formal_tables": sorted(actual_tables),
                "model_tables_missing_from_formal": schema_missing_tables,
                "formal_tables_not_in_current_metadata": sorted(actual_tables - metadata_tables),
                "schema_matches": schema_matches,
            },
            "baseline_counts": counts,
            "knowledge_document_statistics": document_stats,
            "protected_qa_record": qa_summary,
            "formal_huawei_scope": {
                "document_count": len(formal_huawei_rows),
                "chunk_count": huawei_chunk_count,
                "documents": huawei_scope_summary,
            },
            "documents_by_source_sha": documents_by_sha,
            "documents_by_title": documents_by_title,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "BLOCKED_FORMAL_DATABASE_READONLY_CHECK_FAILED",
            "identity": sanitize_url(url),
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:500],
            "formal_writes": 0,
        }
    finally:
        connection.rollback()
        connection.close()


def comparable_metadata(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document.get("metadata_json") or {}
    return {
        "title": document.get("title"),
        "manufacturer": document.get("manufacturer"),
        "product_series": document.get("product_series"),
        "document_type": document.get("document_type"),
        "document_version": metadata.get("document_version"),
        "scope": metadata_scope(metadata),
        "source_sha256": metadata_source_sha(metadata, document.get("source")),
    }


def classify_candidates(
    test_snapshot: dict[str, Any], formal: dict[str, Any]
) -> list[dict[str, Any]]:
    classifications: list[dict[str, Any]] = []
    source_index = formal.get("documents_by_source_sha", {})
    title_index = formal.get("documents_by_title", {})
    for candidate in test_snapshot.get("candidates", []):
        item = {
            "candidate_id": candidate.get("id"),
            "title": candidate.get("title"),
            "source_relative_path": candidate.get("source_relative_path"),
            "source_sha256": candidate.get("source_sha256"),
            "classification": None,
            "action": None,
            "formal_matches": [],
            "reason": None,
        }
        if formal.get("status") != "PASSED":
            item.update(
                classification="FORMAL_COMPARISON_NOT_EXECUTED",
                action="DO_NOT_IMPORT",
                reason="formal_database_preflight_did_not_complete; duplicate_and_conflict_checks_are_unavailable",
            )
            classifications.append(item)
            continue
        if candidate.get("validation_errors"):
            item.update(
                classification="BLOCKED_INVALID_METADATA",
                action="DO_NOT_IMPORT",
                reason="test_candidate_validation_failed",
            )
            classifications.append(item)
            continue
        same_hash = source_index.get(candidate["source_sha256"], [])
        same_title = title_index.get(normalize_title(candidate.get("title")), [])
        if same_hash:
            item["formal_matches"] = [
                {
                    "id": str(row["id"]),
                    "title": row.get("title"),
                    "source_sha256": metadata_source_sha(row.get("metadata_json"), row.get("source")),
                    "chunk_count": int(row.get("chunk_count") or 0),
                    "review_status": row.get("review_status"),
                    "scope": metadata_scope(row.get("metadata_json")),
                }
                for row in same_hash
            ]
            exact_title = any(normalize_title(row.get("title")) == normalize_title(candidate.get("title")) for row in same_hash)
            if not exact_title:
                item.update(
                    classification="SAME_HASH_DIFFERENT_TITLE",
                    action="SKIP_AS_ALIAS",
                    reason="same_verified_source_sha256_is_already_present_under_a_different_title",
                )
            else:
                candidate_metadata = {
                    "title": candidate.get("title"),
                    "manufacturer": candidate.get("manufacturer"),
                    "product_series": candidate.get("product_series"),
                    "document_type": candidate.get("document_type"),
                    "document_version": candidate.get("document_version"),
                    "scope": candidate.get("scope"),
                    "source_sha256": candidate.get("source_sha256"),
                }
                metadata_matches = [comparable_metadata(row) == candidate_metadata for row in same_hash]
                if any(metadata_matches):
                    item.update(
                        classification="ALREADY_PRESENT_IDENTICAL",
                        action="SKIP_NO_WRITE",
                        reason="same_source_sha256_and_comparable_metadata_are_already_present",
                    )
                else:
                    item.update(
                        classification="ALREADY_PRESENT_METADATA_DIFFERENCE",
                        action="BLOCK_FOR_REVIEW",
                        reason="same_source_sha256_exists_but_comparable_metadata_differs",
                    )
        elif same_title:
            item["formal_matches"] = [
                {
                    "id": str(row["id"]),
                    "title": row.get("title"),
                    "source_sha256": metadata_source_sha(row.get("metadata_json"), row.get("source")),
                    "chunk_count": int(row.get("chunk_count") or 0),
                }
                for row in same_title
            ]
            item.update(
                classification="SAME_TITLE_DIFFERENT_HASH",
                action="BLOCK_FOR_REVIEW",
                reason="same_normalized_title_exists_with_a_different_source_sha256",
            )
        else:
            item.update(
                classification="NEW_IMPORT_CANDIDATE",
                action="CREATE_PENDING_THEN_APPROVE_WITH_REVIEW_SERVICE",
                reason="no_matching_formal_source_sha256_or_normalized_title_found",
            )
        classifications.append(item)
    return classifications


def safe_formal_summary(formal: dict[str, Any]) -> dict[str, Any]:
    result = dict(formal)
    result.pop("documents_by_source_sha", None)
    result.pop("documents_by_title", None)
    return result


def static_importer_check() -> dict[str, Any]:
    path = BACKEND_ROOT / "scripts" / "import_competition_knowledge_corpus.py"
    source = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "exists": path.is_file(),
        "sha256": file_sha256(path) if path.is_file() else None,
        "formal_guard_present": "_assert_apply_database" in source and "formal_import" in source,
        "requires_separate_apply_task": True,
        "invoked_by_this_preflight": False,
    }


def pg_dump_version() -> dict[str, Any]:
    executable = Path(r"D:\Work Space\PostgreSQL\bin\pg_dump.exe")
    if not executable.is_file():
        return {"available": False, "path": None, "version": None}
    completed = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, check=False, timeout=15
    )
    return {
        "available": completed.returncode == 0,
        "path": str(executable),
        "version": (completed.stdout or completed.stderr).strip(),
    }


def write_schema_connectivity_check_at(runtime_root: Path) -> dict[str, Any]:
    path = runtime_root / "checks" / "formal_schema_connectivity_check.sql"
    content = """-- Task 28A-R3A schema-only read-only connectivity verification.\n-- No credentials, data rows, password hashes, or content are included.\nBEGIN TRANSACTION READ ONLY;\nSELECT current_database(), current_user, current_setting('transaction_read_only');\nSELECT version_num FROM alembic_version;\nSELECT table_name FROM information_schema.tables\n  WHERE table_schema = 'public' AND table_type = 'BASE TABLE'\n  ORDER BY table_name;\nROLLBACK;\n"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return {"path": path.relative_to(PROJECT_ROOT).as_posix(), "sha256": file_sha256(path)}


def write_schema_connectivity_check() -> dict[str, Any]:
    return write_schema_connectivity_check_at(RUNTIME_ROOT)


def build_status(test_snapshot: dict[str, Any], formal: dict[str, Any], classifications: list[dict[str, Any]]) -> str:
    if formal.get("status") != "PASSED":
        return formal.get("status", "BLOCKED_FORMAL_DATABASE_READONLY_CHECK_FAILED")
    if test_snapshot.get("status") != "PASSED":
        return "BLOCKED_TEST_CANDIDATE_VALIDATION_FAILED"
    if any(item["classification"] in {"ALREADY_PRESENT_METADATA_DIFFERENCE", "SAME_TITLE_DIFFERENT_HASH", "BLOCKED_INVALID_METADATA"} for item in classifications):
        return "PREFLIGHT_BLOCKED_CONFLICT_REVIEW_REQUIRED"
    if classifications and all(
        item["classification"] in {"ALREADY_PRESENT_IDENTICAL", "SAME_HASH_DIFFERENT_TITLE"}
        for item in classifications
    ):
        return "PREFLIGHT_NO_IMPORT_REQUIRED"
    return "PREFLIGHT_READY_AWAITING_APPROVAL"


def report_markdown(plan: dict[str, Any], plan_sha256: str, approval_token: str, protected_ok: bool) -> str:
    totals = plan["totals"]
    formal = plan["formal_preflight"]
    token_display = approval_token or "not issued while preflight is blocked"
    return f"""# Task 28A-R3A Formal Import Preflight\n\nGenerated: {plan['generated_at']}\n\n## Boundary\n\nThis is a dry-run only preflight. The formal database was accessed only with\n`BEGIN TRANSACTION READ ONLY`; formal writes, migration, backup creation, and\nthe importer Apply path were not executed.\n\n## Result\n\n- Preflight status: `{plan['status']}`\n- Test Huawei candidates: `{totals['test_huawei_candidates']}`\n- Valid test Huawei candidates: `{totals['valid_test_huawei_candidates']}`\n- Formal database status: `{formal.get('status')}`\n- Formal write operations: `0`\n- Selected Sungrow documents: `0`\n- Selected media and fault-case annotations: `0`\n- Fresh full backup created: `false`\n- Fresh full backup required before Apply: `true`\n- Protected-file baseline unchanged after preflight: `{str(protected_ok).lower()}`\n\n## Frozen Plan\n\n- Plan: `task28a_r3_formal_import_plan.json`\n- SHA-256: `{plan_sha256}`\n- Required exact approval token: `{token_display}`\n\nAny later Apply must use a fresh PostgreSQL `pg_dump -Fc` backup, revalidate\nthe plan SHA-256 and protected-file baseline, and be separately authorized.\n"""


def update_status_documents(status: str, plan_sha256: str, approval_token: str) -> None:
    delivery_status_path = DOCS_ROOT / "35_task28a_delivery_status.md"
    checkpoint_path = DOCS_ROOT / "36_task28a_checkpoint.md"
    token_display = approval_token or "not issued while preflight is blocked"
    addition = (
        "\n\n## Task 28A-R3A Formal Import Preflight\n\n"
        f"- Status: `{status}`\n"
        "- Mode: dry-run only; no formal database write, migration, or Apply occurred.\n"
        f"- Frozen plan SHA-256: `{plan_sha256}`\n"
        f"- Required exact approval token: `{token_display}`\n"
        "- A fresh `pg_dump -Fc` backup remains mandatory before any separately authorized Apply.\n"
    )
    for path in (delivery_status_path, checkpoint_path):
        if path.is_file():
            current = path.read_text(encoding="utf-8")
            marker = "## Task 28A-R3A Formal Import Preflight"
            if marker in current:
                current = current.split(marker, 1)[0].rstrip() + "\n"
            path.write_text(current.rstrip() + addition, encoding="utf-8", newline="\n")


def read_v1_plan_identity() -> tuple[str | None, str | None]:
    plan_path = DOCS_ROOT / "task28a_r3_formal_import_plan.json"
    if not plan_path.is_file():
        return None, None
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return file_sha256(plan_path), plan.get("status")


def load_runtime_context(
    path: Path | None,
    *,
    runtime_root: Path = R3A_R1_RUNTIME_ROOT,
) -> dict[str, Any]:
    if path is None:
        return {"formal_cluster_runtime_writes_possible": True, "context_recorded": False}
    resolved = path.resolve()
    if not path_under(runtime_root, resolved):
        raise PreflightError("formal runtime context must remain under the active task runtime directory")
    if not resolved.is_file():
        raise PreflightError("formal runtime context file is missing")
    # PowerShell 5.1 writes UTF-8 with a BOM by default; runtime evidence may
    # therefore use either UTF-8 encoding variant.
    context = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if "password" in json.dumps(context, ensure_ascii=False).casefold():
        raise PreflightError("formal runtime context must not contain credentials")
    context["context_recorded"] = True
    context["formal_cluster_runtime_writes_possible"] = True
    return context


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"required {label} is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise PreflightError(f"required {label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise PreflightError(f"required {label} must be a JSON object")
    return payload


def changed_json_paths(expected: Any, actual: Any, prefix: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected) | set(actual))
        changes: list[str] = []
        for key in keys:
            location = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected or key not in actual:
                changes.append(location)
            else:
                changes.extend(changed_json_paths(expected[key], actual[key], location))
        return changes
    if isinstance(expected, list) and isinstance(actual, list):
        changes = []
        for index in range(max(len(expected), len(actual))):
            location = f"{prefix}[{index}]"
            if index >= len(expected) or index >= len(actual):
                changes.append(location)
            else:
                changes.extend(changed_json_paths(expected[index], actual[index], location))
        return changes
    return [] if expected == actual else [prefix or "root"]


def protected_change_scope(v2_baseline_path: Path, current: dict[str, Any]) -> dict[str, Any]:
    prior = load_json(v2_baseline_path, "v2 protected-file baseline")
    prior_files = {item["path"]: item for item in prior.get("files", []) if isinstance(item, dict)}
    current_files = {item["path"]: item for item in current.get("files", []) if isinstance(item, dict)}
    changed_paths = sorted(
        path
        for path in set(prior_files) | set(current_files)
        if prior_files.get(path) != current_files.get(path)
    )
    allowed_paths = {"backend/scripts/import_competition_knowledge_corpus.py"}
    return {
        "v2_aggregate_sha256": prior.get("aggregate_sha256"),
        "current_aggregate_sha256": current.get("aggregate_sha256"),
        "changed_paths": changed_paths,
        "allowed_changed_paths": sorted(path for path in changed_paths if path in allowed_paths),
        "unexpected_changed_paths": sorted(path for path in changed_paths if path not in allowed_paths),
        "authorized_change_scope_verified": all(path in allowed_paths for path in changed_paths)
        and "backend/scripts/import_competition_knowledge_corpus.py" in changed_paths,
    }


def gate_contract_evidence() -> dict[str, Any]:
    acceptance_path = DOCS_ROOT / "task28a_acceptance.json"
    acceptance = load_json(acceptance_path, "Task 28A acceptance")
    _assert_formal_gates(acceptance_path)
    qa = acceptance.get("qa_persistence")
    if not isinstance(qa, dict):
        raise PreflightError("qa_persistence gate payload is invalid")
    results = {key: qa.get(key) is True for key in QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS}
    if qa.get("status") != "PASSED" or not all(results.values()):
        raise PreflightError("formal QA gate contract did not pass")
    return {
        "contract_version": FORMAL_GATE_CONTRACT_VERSION,
        "qa_persistence_status": qa.get("status"),
        "required_boolean_keys": list(QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS),
        "required_boolean_results": results,
        "gate_result": "PASSED",
        "formal_database_connected": False,
        "formal_writes": 0,
        "apply_executed": False,
    }


def gate_contract_test_artifacts() -> list[dict[str, Any]]:
    paths = [BACKEND_ROOT / "tests" / "unit" / "test_task28a_formal_gate_contract.py"]
    artifacts: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            raise PreflightError("required formal gate contract test file is missing")
        artifacts.append(
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": file_sha256(path),
            }
        )
    return artifacts


def enrich_v2_classifications(
    classifications: list[dict[str, Any]], test_snapshot: dict[str, Any]
) -> list[dict[str, Any]]:
    candidates = {item.get("id"): item for item in test_snapshot.get("candidates", [])}
    for item in classifications:
        candidate = candidates.get(item.get("candidate_id"), {})
        item["planned_action"] = item.get("action")
        item["conflicts"] = (
            [item.get("reason")]
            if item.get("classification")
            in {"ALREADY_PRESENT_METADATA_DIFFERENCE", "SAME_TITLE_DIFFERENT_HASH", "BLOCKED_INVALID_METADATA"}
            else []
        )
        item["test_chunk_count"] = candidate.get("chunk_count", 0)
        item["formal_document_id"] = (
            item["formal_matches"][0].get("id") if item.get("formal_matches") else None
        )
        item["formal_chunk_count"] = (
            item["formal_matches"][0].get("chunk_count") if item.get("formal_matches") else None
        )
    return classifications


def run_v2(formal_runtime_context_path: Path | None) -> int:
    """Run Task 28A-R3A-R1 without mutating the preserved v1 plan."""

    runtime_root = R3A_R1_RUNTIME_ROOT
    for directory in ("logs", "checks", "snapshots", "plans"):
        (runtime_root / directory).mkdir(parents=True, exist_ok=True)
    context = load_runtime_context(formal_runtime_context_path)
    protected_before = protected_hash_manifest()
    protected_before_path = runtime_root / "checks" / "protected_baseline_v2.json"
    write_json(protected_before_path, protected_before)

    manifest = load_manifest()
    exclusions = build_exclusions(manifest)
    test_url = make_url(read_dotenv(TEST_ENV_PATH).get("DATABASE_URL", ""))
    formal_url = make_url(read_dotenv(FORMAL_ENV_PATH).get("DATABASE_URL", ""))
    test_snapshot = verify_test_candidates(test_url, manifest)
    test_snapshot_path = runtime_root / "snapshots" / "test_huawei_candidate_snapshot_v2.json"
    write_json(test_snapshot_path, test_snapshot)
    formal = formal_baseline(formal_url, verify_readonly_probe=True)
    formal_snapshot_path = runtime_root / "snapshots" / "formal_database_preimport_snapshot_v2.json"
    write_json(formal_snapshot_path, safe_formal_summary(formal))
    qa_snapshot_path = runtime_root / "snapshots" / "protected_qa_record_snapshot_v2.json"
    write_json(qa_snapshot_path, formal.get("protected_qa_record", {"exists": False, "reason": formal.get("status")}))
    classifications = enrich_v2_classifications(classify_candidates(test_snapshot, formal), test_snapshot)
    schema_check = write_schema_connectivity_check_at(runtime_root)
    protected_after = protected_hash_manifest()
    protected_after_path = runtime_root / "checks" / "protected_baseline_after_v2.json"
    write_json(protected_after_path, protected_after)
    protected_unchanged = protected_before["aggregate_sha256"] == protected_after["aggregate_sha256"]
    status = build_status(test_snapshot, formal, classifications)
    classification_counts = Counter(item["classification"] for item in classifications)
    v1_sha256, v1_status = read_v1_plan_identity()

    plan = {
        "schema_version": "2.0.0",
        "task": "Task 28A-R3A-R1",
        "generated_at": utc_now(),
        "mode": "PREFLIGHT_DRY_RUN_ONLY",
        "status": status,
        "supersedes_plan_sha256": v1_sha256,
        "previous_plan_status": v1_status,
        "formal_apply_performed": False,
        "formal_cluster_runtime_writes_possible": True,
        "formal_business_sql_writes": 0,
        "formal_schema_changes": 0,
        "formal_import_writes": 0,
        "formal_alembic_changes": 0,
        "formal_review_changes": 0,
        "formal_vector_changes": 0,
        "formal_cluster_runtime": context,
        "formal_transaction_policy": "SET default_transaction_read_only=on; BEGIN TRANSACTION READ ONLY",
        "test_database": test_snapshot["identity"],
        "formal_database": sanitize_url(formal_url),
        "expected_alembic_head": EXPECTED_ALEMBIC_HEAD,
        "test_candidate_snapshot": {
            "path": test_snapshot_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(test_snapshot_path),
        },
        "formal_database_snapshot": {
            "path": formal_snapshot_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(formal_snapshot_path),
        },
        "protected_qa_snapshot": {
            "path": qa_snapshot_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(qa_snapshot_path),
        },
        "formal_preflight": safe_formal_summary(formal),
        "candidate_classifications": classifications,
        "exclusions": exclusions,
        "totals": {
            "manifest_documents": len(manifest.get("documents", [])),
            "test_huawei_candidates": test_snapshot.get("candidate_count", 0),
            "valid_test_huawei_candidates": test_snapshot.get("valid_candidate_count", 0),
            "test_huawei_chunks": sum(item.get("chunk_count", 0) for item in test_snapshot.get("candidates", [])),
            "classification_counts": dict(sorted(classification_counts.items())),
            "already_present_identical": classification_counts.get("ALREADY_PRESENT_IDENTICAL", 0),
            "same_hash_different_title": classification_counts.get("SAME_HASH_DIFFERENT_TITLE", 0),
            "metadata_conflicts": classification_counts.get("ALREADY_PRESENT_METADATA_DIFFERENCE", 0),
            "same_title_different_hash_conflicts": classification_counts.get("SAME_TITLE_DIFFERENT_HASH", 0),
            "invalid_candidates": classification_counts.get("BLOCKED_INVALID_METADATA", 0),
            "exclusions": len(exclusions),
            "selected_sungrow_documents": 0,
            "selected_media_assets": 0,
            "selected_fault_case_annotations": 0,
        },
        "safety": {
            "formal_business_sql_writes": 0,
            "schema_changes_executed": 0,
            "alembic_upgrade_executed": False,
            "full_backup_created": False,
            "full_backup_required_before_apply": True,
            "formal_importer_invoked": False,
            "protected_files_unchanged": protected_unchanged,
            "sungrow_imported": False,
            "images_imported": False,
            "user_cases_imported": False,
        },
        "tooling": {
            "importer": static_importer_check(),
            "pg_dump": pg_dump_version(),
            "schema_connectivity_check": schema_check,
        },
        "next_step": {
            "requires_exact_approval_token": status == "PREFLIGHT_READY_AWAITING_APPROVAL",
            "requires_fresh_pg_dump_fc_backup": True,
            "must_revalidate_plan_sha256": True,
            "must_revalidate_protected_baseline": True,
            "must_not_apply_from_this_script": True,
        },
    }
    plan_path = DOCS_ROOT / "task28a_r3_formal_import_plan_v2.json"
    runtime_plan_path = runtime_root / "plans" / "task28a_r3_formal_import_plan_v2.json"
    write_json(plan_path, plan)
    runtime_plan_path.write_bytes(plan_path.read_bytes())
    plan_sha256 = file_sha256(plan_path)
    if plan_sha256 != file_sha256(runtime_plan_path):
        raise PreflightError("v2 plan copy hash mismatch")
    approval_token = (
        f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{plan_sha256}"
        if status == "PREFLIGHT_READY_AWAITING_APPROVAL"
        else None
    )
    token_line = approval_token or "APPROVAL_TOKEN_NOT_ISSUED: v2 preflight is not approval-ready"
    (DOCS_ROOT / "task28a_r3_formal_import_plan_v2.sha256").write_text(
        f"{plan_sha256}  task28a_r3_formal_import_plan_v2.json\n{token_line}\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        runtime_root / "plans" / "task28a_r3_preflight_v2_summary.json",
        {
            "status": status,
            "plan_sha256": plan_sha256,
            "approval_token": approval_token,
            "formal_business_sql_writes": 0,
            "protected_files_unchanged": protected_unchanged,
            "formal_status": formal.get("status"),
        },
    )
    acceptance_path = DOCS_ROOT / "task28a_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8")) if acceptance_path.is_file() else {}
    acceptance["formal_import_preflight_r3a_r1"] = {
        "status": status,
        "executed": True,
        "formal_apply_executed": False,
        "formal_database_writes": 0,
        "plan_sha256": plan_sha256,
        "approval_token": approval_token,
        "fresh_backup_required_before_apply": True,
        "protected_files_unchanged": protected_unchanged,
    }
    write_json(acceptance_path, acceptance)
    print(
        json.dumps(
            {
                "status": status,
                "plan_sha256": plan_sha256,
                "approval_token": approval_token,
                "formal_business_sql_writes": 0,
                "test_valid_candidates": test_snapshot.get("valid_candidate_count", 0),
                "classification_counts": dict(sorted(classification_counts.items())),
                "formal_status": formal.get("status"),
                "protected_files_unchanged": protected_unchanged,
            },
            ensure_ascii=False,
        )
    )
    return 0


def v3_report_markdown(plan: dict[str, Any], plan_sha256: str, approval_token: str | None) -> str:
    totals = plan["totals"]
    safety = plan["safety"]
    formal = plan["formal_preflight"]
    token_display = approval_token or "not issued because the v3 preflight is blocked"
    return f"""# Task 28A-R3A-R2 Formal Gate Contract Repair and v3 Preflight

Generated: {plan['generated_at']}

## Boundary

This task repaired only the formal-import gate contract and completed a new
read-only preflight. It did not execute a formal import, a backup, a schema
change, an Alembic operation, a vector rebuild, or a provider call.

## Gate Contract

- Contract version: `{plan['importer']['gate_contract_version']}`
- QA status: `{plan['qa_persistence_contract']['expected_status']}`
- Required QA boolean checks: `{len(plan['qa_persistence_contract']['required_boolean_keys'])}`
- Static gate result: `{plan['gate_contract_evidence']['gate_result']}`

## Read-only Preflight Result

- Status: `{plan['status']}`
- Formal database status: `{formal.get('status')}`
- Formal documents / chunks: `{formal.get('baseline_counts', {}).get('knowledge_documents')}` / `{formal.get('baseline_counts', {}).get('knowledge_chunks')}`
- Test Huawei candidates / chunks: `{totals['test_huawei_candidates']}` / `{totals['test_huawei_chunks']}`
- New import candidates / estimated chunks: `{totals['new_import_candidates']}` / `{totals['estimated_new_chunks']}`
- Selected Sungrow / media / user cases: `{totals['selected_sungrow_documents']}` / `{totals['selected_media_assets']}` / `{totals['selected_user_cases']}`
- Protected QA summary unchanged: `{str(plan['protected_qa_record']['unchanged_since_v2']).lower()}`
- Baseline changed since v2: `{str(plan['baseline_comparison']['baseline_changed_since_v2']).lower()}`

## Frozen v3 Plan

- Plan: `task28a_r3_formal_import_plan_v3.json`
- SHA-256: `{plan_sha256}`
- Required exact approval token: `{token_display}`
- Fresh full backup created: `{str(safety['fresh_full_backup_created']).lower()}`
- Fresh full backup required before a separately authorized Apply: `{str(safety['fresh_full_backup_required_before_apply']).lower()}`

The preserved v1 and v2 plans remain historical evidence. The v2 token is
revoked for Apply because it binds the pre-repair importer hash.
"""


def append_v3_status_documents(status: str, plan_sha256: str, approval_token: str | None) -> None:
    token_display = approval_token or "not issued because the v3 preflight is blocked"
    addition = (
        "\n\n## Task 28A-R3A-R2 Gate Contract Repair and v3 Preflight\n\n"
        f"- Status: `{status}`\n"
        "- Mode: static gate validation plus formal/test PostgreSQL read-only preflight only.\n"
        "- Formal database business writes, schema changes, backup creation, and Apply: `0`.\n"
        f"- Frozen v3 plan SHA-256: `{plan_sha256}`\n"
        f"- Required exact v3 approval token: `{token_display}`\n"
        "- The v2 token is historical evidence only and is revoked for Apply.\n"
        "- A fresh `pg_dump -Fc` backup remains required before any separately authorized Apply.\n"
    )
    for name in (
        "35_task28a_delivery_status.md",
        "36_task28a_checkpoint.md",
        "43_task28a_r3_formal_import_preflight.md",
        "44_formal_database_reachability_and_preflight_rerun.md",
    ):
        path = DOCS_ROOT / name
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        marker = "## Task 28A-R3A-R2 Gate Contract Repair and v3 Preflight"
        if marker in current:
            current = current.split(marker, 1)[0].rstrip()
        path.write_text(current.rstrip() + addition, encoding="utf-8", newline="\n")


def run_v3(formal_runtime_context_path: Path | None) -> int:
    """Create the Task 28A-R3A-R2 v3 plan through read-only verification only."""

    runtime_root = R3A_R2_RUNTIME_ROOT
    for directory in ("baseline", "tests", "logs", "snapshots", "plans", "checks"):
        (runtime_root / directory).mkdir(parents=True, exist_ok=True)

    pre_repair = load_json(runtime_root / "baseline" / "pre_repair_baseline.json", "pre-repair baseline")
    if pre_repair.get("importer_sha256") != EXPECTED_PRE_REPAIR_IMPORTER_SHA256:
        raise PreflightError("BLOCKED_IMPORTER_BASELINE_CHANGED_BEFORE_REPAIR")
    v2_plan_path = DOCS_ROOT / "task28a_r3_formal_import_plan_v2.json"
    if file_sha256(v2_plan_path) != EXPECTED_V2_PLAN_SHA256:
        raise PreflightError("v2 frozen plan SHA-256 does not match the recorded historical value")
    v2_plan = load_json(v2_plan_path, "v2 frozen plan")
    if v2_plan.get("status") != "PREFLIGHT_READY_AWAITING_APPROVAL":
        raise PreflightError("v2 frozen plan status is not the expected historical preflight status")

    gate_evidence = gate_contract_evidence()
    write_json(runtime_root / "checks" / "formal_gate_contract_validation.json", gate_evidence)
    gate_test_artifacts = gate_contract_test_artifacts()
    write_json(runtime_root / "checks" / "formal_gate_contract_test_artifacts.json", gate_test_artifacts)
    context = load_runtime_context(formal_runtime_context_path, runtime_root=runtime_root)
    protected_before = protected_hash_manifest()
    write_json(runtime_root / "checks" / "protected_baseline_before_v3.json", protected_before)
    protected_scope = protected_change_scope(
        R3A_R1_RUNTIME_ROOT / "checks" / "protected_baseline_v2.json", protected_before
    )
    write_json(runtime_root / "checks" / "protected_change_scope_v3.json", protected_scope)

    manifest = load_manifest()
    exclusions = build_exclusions(manifest)
    test_url = make_url(read_dotenv(TEST_ENV_PATH).get("DATABASE_URL", ""))
    formal_url = make_url(read_formal_database_url())
    test_snapshot = verify_test_candidates(test_url, manifest)
    test_snapshot_path = runtime_root / "snapshots" / "test_huawei_candidate_snapshot_v3.json"
    write_json(test_snapshot_path, test_snapshot)
    formal = formal_baseline(formal_url, verify_readonly_probe=True)
    formal_summary = safe_formal_summary(formal)
    formal_snapshot_path = runtime_root / "snapshots" / "formal_database_preimport_snapshot_v3.json"
    write_json(formal_snapshot_path, formal_summary)
    qa_snapshot = formal.get("protected_qa_record", {"exists": False, "reason": formal.get("status")})
    qa_snapshot_path = runtime_root / "snapshots" / "protected_qa_record_snapshot_v3.json"
    write_json(qa_snapshot_path, qa_snapshot)
    classifications = enrich_v2_classifications(classify_candidates(test_snapshot, formal), test_snapshot)
    protected_after = protected_hash_manifest()
    write_json(runtime_root / "checks" / "protected_baseline_after_v3.json", protected_after)

    v2_formal = v2_plan.get("formal_preflight") if isinstance(v2_plan.get("formal_preflight"), dict) else {}
    baseline_changes = changed_json_paths(v2_formal, formal_summary)
    previous_qa = v2_formal.get("protected_qa_record") if isinstance(v2_formal.get("protected_qa_record"), dict) else {}
    protected_qa_unchanged = (
        qa_snapshot.get("exists") is True
        and qa_snapshot.get("summary_row_sha256") == previous_qa.get("summary_row_sha256")
    )
    baseline_comparison = {
        "v2_plan_sha256": EXPECTED_V2_PLAN_SHA256,
        "baseline_changed_since_v2": bool(baseline_changes),
        "changed_paths": baseline_changes,
        "comparison_scope": "complete safe_formal_summary from v2 and v3 read-only snapshots",
    }
    write_json(runtime_root / "checks" / "formal_baseline_comparison_v2_to_v3.json", baseline_comparison)

    status = build_status(test_snapshot, formal, classifications)
    status_map = {
        "PREFLIGHT_READY_AWAITING_APPROVAL": "PREFLIGHT_V3_READY_AWAITING_APPROVAL",
        "PREFLIGHT_NO_IMPORT_REQUIRED": "PREFLIGHT_V3_NO_IMPORT_REQUIRED",
        "PREFLIGHT_BLOCKED_CONFLICT_REVIEW_REQUIRED": "PREFLIGHT_V3_BLOCKED_CONFLICT_REVIEW_REQUIRED",
    }
    status = status_map.get(status, status)
    if not protected_scope["authorized_change_scope_verified"] or protected_before != protected_after:
        status = "SECURITY_BOUNDARY_VIOLATION"
    elif not protected_qa_unchanged:
        status = "PREFLIGHT_V3_BLOCKED_PROTECTED_RECORD_CHANGED"
    elif baseline_changes:
        status = "PREFLIGHT_V3_BLOCKED_UNEXPLAINED_BASELINE_CHANGE"

    classification_counts = Counter(item["classification"] for item in classifications)
    importer_path = BACKEND_ROOT / "scripts" / "import_competition_knowledge_corpus.py"
    importer_sha256 = file_sha256(importer_path)
    estimated_new_chunks = sum(
        int(item.get("test_chunk_count") or 0)
        for item in classifications
        if item.get("classification") == "NEW_IMPORT_CANDIDATE"
    )
    schema_check = write_schema_connectivity_check_at(runtime_root)
    issuance_conditions = {
        "static_gate_contract_passed": gate_evidence.get("gate_result") == "PASSED",
        "formal_identity_and_readonly_passed": formal.get("status") == "PASSED",
        "readonly_write_probe_rejected": formal.get("readonly_session_evidence", {}).get("readonly_write_probe_rejected") not in {None, "not_executed"},
        "alembic_head_matches": formal.get("alembic_current") == EXPECTED_ALEMBIC_HEAD,
        "schema_matches": formal.get("metadata_table_comparison", {}).get("schema_matches") is True,
        "protected_qa_unchanged": protected_qa_unchanged,
        "formal_comparison_not_executed": classification_counts.get("FORMAL_COMPARISON_NOT_EXECUTED", 0) == 0,
        "metadata_conflicts": classification_counts.get("ALREADY_PRESENT_METADATA_DIFFERENCE", 0) == 0,
        "same_title_different_hash_conflicts": classification_counts.get("SAME_TITLE_DIFFERENT_HASH", 0) == 0,
        "invalid_candidates": classification_counts.get("BLOCKED_INVALID_METADATA", 0) == 0,
        "selected_sungrow_documents": 0,
        "selected_media_assets": 0,
        "selected_user_cases": 0,
        "formal_business_sql_writes": 0,
        "authorized_protected_change_scope": protected_scope["authorized_change_scope_verified"],
        "baseline_unchanged_or_explained": not baseline_changes,
    }
    issuance_ready = (
        status == "PREFLIGHT_V3_READY_AWAITING_APPROVAL"
        and all(
            value is True or (key.startswith("selected_") and value == 0) or (key == "formal_business_sql_writes" and value == 0)
            for key, value in issuance_conditions.items()
        )
    )

    plan = {
        "schema_version": "3.0.0",
        "task": "Task 28A-R3A-R2",
        "generated_at": utc_now(),
        "mode": "PREFLIGHT_DRY_RUN_ONLY",
        "status": status,
        "supersedes_plan_sha256": EXPECTED_V2_PLAN_SHA256,
        "previous_plan_status": "PREFLIGHT_READY_AWAITING_APPROVAL",
        "previous_apply_attempt": {
            "executed": False,
            "stopped_before_formal_start": True,
            "reason": "FORMAL_GATE_QA_PERSISTENCE_CONTRACT_MISMATCH",
        },
        "formal_apply_performed": False,
        "formal_cluster_runtime": context,
        "formal_transaction_policy": "SET default_transaction_read_only=on; BEGIN TRANSACTION READ ONLY",
        "importer": {
            "path": importer_path.relative_to(PROJECT_ROOT).as_posix(),
            "old_sha256": EXPECTED_PRE_REPAIR_IMPORTER_SHA256,
            "new_sha256": importer_sha256,
            "gate_contract_version": FORMAL_GATE_CONTRACT_VERSION,
            "repair_summary": "QA status is validated separately; seven named fields require the singleton boolean True.",
        },
        "qa_persistence_contract": {
            "expected_status": "PASSED",
            "required_boolean_keys": list(QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS),
            "all_required_checks_true": True,
        },
        "gate_contract_evidence": gate_evidence,
        "gate_contract_test_artifacts": gate_test_artifacts,
        "test_database": test_snapshot["identity"],
        "formal_database": sanitize_url(formal_url),
        "expected_alembic_head": EXPECTED_ALEMBIC_HEAD,
        "test_candidate_snapshot": {
            "path": test_snapshot_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(test_snapshot_path),
        },
        "formal_database_snapshot": {
            "path": formal_snapshot_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(formal_snapshot_path),
        },
        "protected_qa_snapshot": {
            "path": qa_snapshot_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(qa_snapshot_path),
        },
        "formal_preflight": formal_summary,
        "formal_baseline": formal_summary.get("baseline_counts", {}),
        "baseline_comparison": baseline_comparison,
        "protected_qa_record": {
            "id": PROTECTED_QA_ID,
            "trace_id": PROTECTED_QA_TRACE_ID,
            "summary_row_sha256": qa_snapshot.get("summary_row_sha256"),
            "unchanged_since_v2": protected_qa_unchanged,
            "request_id_storage": qa_snapshot.get("request_id_verification"),
        },
        "protected_change_scope": protected_scope,
        "candidate_classifications": classifications,
        "exclusions": exclusions,
        "totals": {
            "manifest_documents": len(manifest.get("documents", [])),
            "test_huawei_candidates": test_snapshot.get("candidate_count", 0),
            "valid_test_huawei_candidates": test_snapshot.get("valid_candidate_count", 0),
            "test_huawei_chunks": sum(item.get("chunk_count", 0) for item in test_snapshot.get("candidates", [])),
            "classification_counts": dict(sorted(classification_counts.items())),
            "already_present_identical": classification_counts.get("ALREADY_PRESENT_IDENTICAL", 0),
            "same_hash_different_title": classification_counts.get("SAME_HASH_DIFFERENT_TITLE", 0),
            "metadata_conflicts": classification_counts.get("ALREADY_PRESENT_METADATA_DIFFERENCE", 0),
            "same_title_different_hash_conflicts": classification_counts.get("SAME_TITLE_DIFFERENT_HASH", 0),
            "invalid_candidates": classification_counts.get("BLOCKED_INVALID_METADATA", 0),
            "formal_comparison_not_executed": classification_counts.get("FORMAL_COMPARISON_NOT_EXECUTED", 0),
            "new_import_candidates": classification_counts.get("NEW_IMPORT_CANDIDATE", 0),
            "estimated_new_chunks": estimated_new_chunks,
            "exclusions": len(exclusions),
            "selected_sungrow_documents": 0,
            "selected_media_assets": 0,
            "selected_fault_case_annotations": 0,
            "selected_user_cases": 0,
        },
        "safety": {
            "formal_business_sql_writes": 0,
            "formal_schema_changes": 0,
            "formal_alembic_changes": 0,
            "formal_import_executed": False,
            "fresh_full_backup_created": False,
            "fresh_full_backup_required_before_apply": True,
            "provider_calls": 0,
            "vector_rebuild": False,
            "formal_importer_invoked": False,
            "sungrow_imported": False,
            "images_imported": False,
            "user_cases_imported": False,
        },
        "tooling": {
            "importer": static_importer_check(),
            "pg_dump": pg_dump_version(),
            "schema_connectivity_check": schema_check,
        },
        "issuance_conditions": issuance_conditions,
        "next_step": {
            "requires_exact_approval_token": issuance_ready,
            "requires_fresh_pg_dump_fc_backup": True,
            "must_revalidate_plan_sha256": True,
            "must_revalidate_protected_baseline": True,
            "must_not_apply_from_this_script": True,
        },
    }
    plan_path = DOCS_ROOT / "task28a_r3_formal_import_plan_v3.json"
    runtime_plan_path = runtime_root / "plans" / "task28a_r3_formal_import_plan_v3.json"
    write_json(plan_path, plan)
    runtime_plan_path.write_bytes(plan_path.read_bytes())
    plan_sha256 = file_sha256(plan_path)
    if plan_sha256 != file_sha256(runtime_plan_path):
        raise PreflightError("v3 plan copy hash mismatch")
    approval_token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{plan_sha256}" if issuance_ready else None
    if approval_token:
        from import_competition_knowledge_corpus import _assert_formal_approval_token

        _assert_formal_approval_token(approval_token)
    token_line = approval_token or "APPROVAL_TOKEN_NOT_ISSUED: v3 preflight is blocked"
    (DOCS_ROOT / "task28a_r3_formal_import_plan_v3.sha256").write_text(
        f"{plan_sha256}  task28a_r3_formal_import_plan_v3.json\n{token_line}\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        runtime_root / "plans" / "task28a_r3_preflight_v3_summary.json",
        {
            "status": status,
            "plan_sha256": plan_sha256,
            "approval_token": approval_token,
            "formal_business_sql_writes": 0,
            "formal_schema_changes": 0,
            "formal_import_executed": False,
            "fresh_full_backup_created": False,
            "protected_qa_unchanged": protected_qa_unchanged,
            "baseline_changed_since_v2": bool(baseline_changes),
        },
    )
    report_path = DOCS_ROOT / "45_formal_import_gate_contract_repair_and_preflight_v3.md"
    report_path.write_text(v3_report_markdown(plan, plan_sha256, approval_token), encoding="utf-8", newline="\n")
    append_v3_status_documents(status, plan_sha256, approval_token)
    acceptance_path = DOCS_ROOT / "task28a_acceptance.json"
    acceptance = load_json(acceptance_path, "Task 28A acceptance")
    acceptance["formal_import_preflight_r3a_r2"] = {
        "status": status,
        "executed": True,
        "formal_apply_executed": False,
        "formal_database_writes": 0,
        "formal_schema_changes": 0,
        "plan_sha256": plan_sha256,
        "approval_token": approval_token,
        "supersedes_plan_sha256": EXPECTED_V2_PLAN_SHA256,
        "v2_token_revoked_for_apply": True,
        "new_importer_sha256": importer_sha256,
        "gate_contract_version": FORMAL_GATE_CONTRACT_VERSION,
        "formal_readonly_probe_rejected": formal.get("readonly_session_evidence", {}).get("readonly_write_probe_rejected") not in {None, "not_executed"},
        "protected_qa_digest_unchanged": protected_qa_unchanged,
        "baseline_changed_since_v2": bool(baseline_changes),
        "fresh_backup_required_before_apply": True,
        "protected_change_scope_verified": protected_scope["authorized_change_scope_verified"],
    }
    write_json(acceptance_path, acceptance)
    print(
        json.dumps(
            {
                "status": status,
                "plan_sha256": plan_sha256,
                "approval_token": approval_token,
                "formal_business_sql_writes": 0,
                "formal_schema_changes": 0,
                "test_valid_candidates": test_snapshot.get("valid_candidate_count", 0),
                "classification_counts": dict(sorted(classification_counts.items())),
                "formal_status": formal.get("status"),
                "protected_qa_unchanged": protected_qa_unchanged,
                "baseline_changed_since_v2": bool(baseline_changes),
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--v2", action="store_true", help="run the Task 28A-R3A-R1 v2 read-only preflight")
    parser.add_argument("--v3", action="store_true", help="run the Task 28A-R3A-R2 v3 read-only preflight")
    parser.add_argument("--formal-runtime-context", type=Path, help="sanitized runtime context under the active task runtime")
    args = parser.parse_args()
    if args.apply:
        raise PreflightError("Task 28A-R3A is plan-only. --apply is refused before any database connection.")
    if args.v2 and args.v3:
        raise PreflightError("select either --v2 or --v3, never both")
    if args.v2:
        return run_v2(args.formal_runtime_context)
    if args.v3:
        return run_v3(args.formal_runtime_context)

    for directory in ("preflight", "plans", "snapshots", "logs", "backups", "checks"):
        (RUNTIME_ROOT / directory).mkdir(parents=True, exist_ok=True)
    protected_before = protected_hash_manifest()
    write_json(RUNTIME_ROOT / "preflight" / "protected_baseline.json", protected_before)
    manifest = load_manifest()
    exclusions = build_exclusions(manifest)
    test_url = make_url(read_dotenv(TEST_ENV_PATH).get("DATABASE_URL", ""))
    formal_url = make_url(read_dotenv(FORMAL_ENV_PATH).get("DATABASE_URL", ""))

    test_snapshot = verify_test_candidates(test_url, manifest)
    write_json(RUNTIME_ROOT / "snapshots" / "test_huawei_candidate_snapshot.json", test_snapshot)
    formal = formal_baseline(formal_url)
    classifications = classify_candidates(test_snapshot, formal)
    schema_check = write_schema_connectivity_check()
    protected_after = protected_hash_manifest()
    write_json(RUNTIME_ROOT / "preflight" / "protected_baseline_after.json", protected_after)
    protected_unchanged = protected_before["aggregate_sha256"] == protected_after["aggregate_sha256"]
    status = build_status(test_snapshot, formal, classifications)

    classification_counts = Counter(item["classification"] for item in classifications)
    plan = {
        "schema_version": "1.0.0",
        "task": "Task 28A-R3A",
        "generated_at": utc_now(),
        "mode": "PREFLIGHT_DRY_RUN_ONLY",
        "status": status,
        "formal_apply_performed": False,
        "formal_write_operations": 0,
        "formal_transaction_policy": "BEGIN TRANSACTION READ ONLY",
        "test_database": test_snapshot["identity"],
        "formal_database": sanitize_url(formal_url),
        "expected_alembic_head": EXPECTED_ALEMBIC_HEAD,
        "test_candidate_snapshot": {
            "path": (RUNTIME_ROOT / "snapshots" / "test_huawei_candidate_snapshot.json").relative_to(PROJECT_ROOT).as_posix(),
            "sha256": file_sha256(RUNTIME_ROOT / "snapshots" / "test_huawei_candidate_snapshot.json"),
        },
        "formal_preflight": safe_formal_summary(formal),
        "candidate_classifications": classifications,
        "exclusions": exclusions,
        "totals": {
            "manifest_documents": len(manifest.get("documents", [])),
            "test_huawei_candidates": test_snapshot.get("candidate_count", 0),
            "valid_test_huawei_candidates": test_snapshot.get("valid_candidate_count", 0),
            "classification_counts": dict(sorted(classification_counts.items())),
            "exclusions": len(exclusions),
            "selected_sungrow_documents": 0,
            "selected_media_assets": 0,
            "selected_fault_case_annotations": 0,
        },
        "safety": {
            "sql_write_statements_executed": 0,
            "schema_changes_executed": 0,
            "alembic_upgrade_executed": False,
            "full_backup_created": False,
            "full_backup_required_before_apply": True,
            "formal_importer_invoked": False,
            "protected_files_unchanged": protected_unchanged,
            "sungrow_imported": False,
            "images_imported": False,
            "user_cases_imported": False,
        },
        "tooling": {
            "importer": static_importer_check(),
            "pg_dump": pg_dump_version(),
            "schema_connectivity_check": schema_check,
        },
        "next_step": {
            "requires_exact_approval_token": True,
            "requires_fresh_pg_dump_fc_backup": True,
            "must_revalidate_plan_sha256": True,
            "must_revalidate_protected_baseline": True,
            "must_not_apply_from_this_script": True,
        },
    }
    plan_path = DOCS_ROOT / "task28a_r3_formal_import_plan.json"
    runtime_plan_path = RUNTIME_ROOT / "plans" / "task28a_r3_formal_import_plan.json"
    write_json(plan_path, plan)
    runtime_plan_path.write_bytes(plan_path.read_bytes())
    plan_sha256 = file_sha256(plan_path)
    if plan_sha256 != file_sha256(runtime_plan_path):
        raise PreflightError("plan copy hash mismatch")
    approval_token = (
        f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{plan_sha256}"
        if status == "PREFLIGHT_READY_AWAITING_APPROVAL"
        else None
    )
    sha_path = DOCS_ROOT / "task28a_r3_formal_import_plan.sha256"
    token_line = approval_token or "APPROVAL_TOKEN_NOT_ISSUED: preflight is blocked"
    sha_path.write_text(
        f"{plan_sha256}  task28a_r3_formal_import_plan.json\n{token_line}\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        RUNTIME_ROOT / "plans" / "task28a_r3_preflight_summary.json",
        {
            "status": status,
            "plan_sha256": plan_sha256,
            "approval_token": approval_token,
            "formal_write_operations": 0,
            "protected_files_unchanged": protected_unchanged,
        },
    )
    report_path = DOCS_ROOT / "43_task28a_r3_formal_import_preflight.md"
    report_path.write_text(
        report_markdown(plan, plan_sha256, approval_token, protected_unchanged),
        encoding="utf-8",
        newline="\n",
    )
    update_status_documents(status, plan_sha256, approval_token)
    acceptance_path = DOCS_ROOT / "task28a_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8")) if acceptance_path.is_file() else {}
    acceptance["formal_import_preflight_r3a"] = {
        "status": status,
        "executed": True,
        "formal_apply_executed": False,
        "formal_database_writes": 0,
        "plan_sha256": plan_sha256,
        "approval_token": approval_token,
        "fresh_backup_required_before_apply": True,
        "protected_files_unchanged": protected_unchanged,
    }
    write_json(acceptance_path, acceptance)
    print(
        json.dumps(
            {
                "status": status,
                "plan_sha256": plan_sha256,
                "approval_token": approval_token,
                "formal_write_operations": 0,
                "test_valid_candidates": test_snapshot.get("valid_candidate_count", 0),
                "classification_counts": dict(sorted(classification_counts.items())),
                "formal_status": formal.get("status"),
                "protected_files_unchanged": protected_unchanged,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreflightError as exc:
        print(f"PRECHECK_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2)
