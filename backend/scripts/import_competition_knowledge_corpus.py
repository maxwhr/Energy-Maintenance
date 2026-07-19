from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from starlette.datastructures import Headers


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = Path(__file__).resolve().parent
for import_root in (BACKEND_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.core.config import get_settings  # noqa: E402
from app.models import User  # noqa: E402
from app.repositories.knowledge_repository import KnowledgeRepository  # noqa: E402
from app.services.knowledge_service import KnowledgeService, KnowledgeServiceError  # noqa: E402
from app.services.review_service import ReviewService, ReviewServiceError  # noqa: E402
from task28a_path_safety import PathBoundaryError, assert_project_path  # noqa: E402


CORPUS_ROOT = PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1"
DEFAULT_SOURCE_ROOT = CORPUS_ROOT / "raw"
DEFAULT_MANIFEST = CORPUS_ROOT / "manifests" / "knowledge_import_manifest.json"
DEFAULT_REPORT = CORPUS_ROOT / "import_reports" / "knowledge_import_result.json"
ACCEPTANCE_PATH = PROJECT_ROOT / "docs" / "project_audit" / "task28a_acceptance.json"
V3_FORMAL_PLAN_PATH = PROJECT_ROOT / "docs" / "project_audit" / "task28a_r3_formal_import_plan_v3.json"
TEST_DATABASE = "energy_maintenance_task27a_test"
FORMAL_DATABASE = "energy_maintenance"
FORMAL_DATABASE_HOST = "127.0.0.1"
FORMAL_DATABASE_PORT = 55432
FORMAL_DATABASE_USER = "energy_user"
ALLOWED_DOCUMENT_TYPES = {
    "manual",
    "alarm_code",
    "sop",
    "fault_case",
    "inspection_standard",
    "maintenance_record",
}
FORMAL_GATE_CONTRACT_VERSION = "task28a_formal_gate_v2"
QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS = (
    "concurrent_idempotent",
    "one_request_one_record",
    "preview_zero_write",
    "record_center_visible",
    "rollback_verified",
    "same_request_id_idempotent",
    "trace_unique",
)


class ImportSafetyError(RuntimeError):
    pass


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    target = assert_project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = assert_project_path(target.with_name(f".{target.name}.task28a.tmp"))
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def _safe_project_path(
    value: str | os.PathLike[str],
    *,
    label: str,
    must_exist: bool = False,
) -> Path:
    """Reject relative, traversal, and resolved-outside project paths before Apply."""

    candidate = Path(value)
    if not candidate.is_absolute():
        raise ImportSafetyError(f"{label} must be an absolute path")
    if ".." in candidate.parts:
        raise ImportSafetyError(f"{label} must not contain '..'")
    try:
        return assert_project_path(candidate, must_exist=must_exist)
    except PathBoundaryError as exc:
        raise ImportSafetyError(f"{label} must remain inside the project root") from exc


def _validate_report_path(report_path: Path) -> Path:
    """Validate and probe the report destination before any database connection."""

    target = _safe_project_path(report_path, label="report path")
    if target.exists() and target.is_dir():
        raise ImportSafetyError("report path must identify a file")
    parent = _safe_project_path(target.parent, label="report parent directory")
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = _safe_project_path(parent / f".{target.name}.{uuid4().hex}.preflight", label="report probe path")
        with probe.open("x", encoding="utf-8") as handle:
            handle.write("task28a report-path preflight\n")
        probe.unlink()
    except OSError as exc:
        raise ImportSafetyError(f"report parent directory is not writable: {parent}") from exc
    return target


def _validate_upload_directory(*, formal_import: bool) -> Path:
    """Resolve the exact KnowledgeService upload root without creating it after commit."""

    configured = Path(get_settings().UPLOAD_DIR) if formal_import else BACKEND_ROOT / "storage" / "tmp" / "task28a_test_uploads"
    if not configured.is_absolute():
        configured = BACKEND_ROOT / configured
    upload_root = _safe_project_path(configured, label="upload/storage path")
    frontend_root = (PROJECT_ROOT / "frontend").resolve()
    try:
        upload_root.relative_to(frontend_root)
    except ValueError:
        return upload_root
    raise ImportSafetyError("upload/storage path must not be under frontend")


def _validate_backup_evidence(path: Path | None, expected_sha256: str | None) -> tuple[Path, str]:
    if path is None or not expected_sha256:
        raise ImportSafetyError("formal import requires --backup-evidence-path and --backup-evidence-sha256")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ImportSafetyError("backup evidence SHA-256 must be a 64-character hexadecimal value")
    backup_path = _safe_project_path(path, label="backup evidence path", must_exist=True)
    if not backup_path.is_file() or backup_path.suffix.lower() != ".dump":
        raise ImportSafetyError("backup evidence path must be an existing .dump file")
    actual_sha256 = _hash_file(backup_path)
    if actual_sha256 != expected_sha256.lower():
        raise ImportSafetyError("backup evidence SHA-256 does not match the supplied value")
    return backup_path, actual_sha256


def _validate_database_target(database_url: str, *, formal_import: bool) -> str:
    database_name = _database_name(database_url)
    if not formal_import:
        return database_name
    parsed = make_url(database_url)
    if (
        parsed.host != FORMAL_DATABASE_HOST
        or parsed.port != FORMAL_DATABASE_PORT
        or parsed.username != FORMAL_DATABASE_USER
        or database_name != FORMAL_DATABASE
    ):
        raise ImportSafetyError("formal import database target does not match the approved host, port, user, and database")
    return database_name


def _validate_formal_candidate_scope(selected: list[dict[str, Any]]) -> None:
    """Bind the selected source hashes to the frozen Huawei-only v3 plan."""

    plan_path = _safe_project_path(V3_FORMAL_PLAN_PATH, label="formal plan path", must_exist=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    classifications = plan.get("candidate_classifications")
    if not isinstance(classifications, list):
        raise ImportSafetyError("formal import plan candidate classifications are invalid")
    planned = {
        str(item.get("source_sha256"))
        for item in classifications
        if isinstance(item, Mapping) and item.get("classification") == "NEW_IMPORT_CANDIDATE"
    }
    selected_hashes = {str(item.get("sha256")) for item in selected}
    if len(planned) != 10 or selected_hashes != planned:
        raise ImportSafetyError("formal import candidates do not exactly match the frozen Huawei v3 plan")
    for item in selected:
        if (
            item.get("manufacturer_normalized") != "huawei"
            or item.get("scope") != "huawei_sun2000_competition_v1"
            or item.get("document_type") == "fault_case"
        ):
            raise ImportSafetyError("formal import selection contains a non-Huawei or excluded candidate")


def _validate_apply_preflight(
    *,
    args: argparse.Namespace,
    database_url: str,
    selected: list[dict[str, Any]],
) -> dict[str, str | None]:
    """Complete every static guard before engine creation or database access."""

    database_name = _validate_database_target(database_url, formal_import=bool(args.formal_import))
    _validate_upload_directory(formal_import=bool(args.formal_import))
    if not args.formal_import:
        _assert_apply_database(database_name, formal_import=False)
        return {"database_name": database_name, "backup_evidence_sha256": None}

    if args.manufacturer != "huawei" or not args.approve_huawei or args.resume:
        raise ImportSafetyError(
            "formal import requires --manufacturer huawei, --approve-huawei, and no --resume flag"
        )
    _safe_project_path(V3_FORMAL_PLAN_PATH, label="formal plan path", must_exist=True)
    _safe_project_path(ACCEPTANCE_PATH, label="acceptance path", must_exist=True)
    _assert_apply_database(database_name, formal_import=True, approval_token=args.approval_token)
    backup_path, backup_sha256 = _validate_backup_evidence(
        args.backup_evidence_path,
        args.backup_evidence_sha256,
    )
    _validate_formal_candidate_scope(selected)
    return {
        "database_name": database_name,
        "backup_evidence_path": str(backup_path),
        "backup_evidence_sha256": backup_sha256,
    }


def _load_manifest(path: Path, source_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = assert_project_path(path, must_exist=True)
    raw_root = assert_project_path(source_root, must_exist=True)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ImportSafetyError("manifest documents must be a list")

    verified: list[dict[str, Any]] = []
    for document in documents:
        relative = Path(document["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ImportSafetyError(f"unsafe relative path: {relative}")
        source_path = assert_project_path(raw_root / relative, must_exist=True)
        try:
            source_path.relative_to(raw_root.resolve())
        except ValueError as exc:
            raise ImportSafetyError(f"manifest path escapes source root: {relative}") from exc
        if source_path.stat().st_size != int(document["size_bytes"]):
            raise ImportSafetyError(f"size mismatch: {relative}")
        actual_hash = _hash_file(source_path)
        if actual_hash != document["sha256"]:
            raise ImportSafetyError(f"SHA-256 mismatch: {relative}")
        verified.append({**document, "verified_source_path": source_path})
    return payload, verified


def _selected_documents(documents: list[dict[str, Any]], manufacturer: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in documents:
        normalized = item["manufacturer_normalized"]
        if manufacturer != "all" and normalized != manufacturer:
            continue
        if not item.get("selected_for_test_import"):
            continue
        if item.get("document_type") not in ALLOWED_DOCUMENT_TYPES:
            continue
        selected.append(item)
    return selected


def _database_name(database_url: str) -> str:
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql" or not parsed.database:
        raise ImportSafetyError("database URL must identify a PostgreSQL database")
    return parsed.database


def _assert_apply_database(
    database_name: str,
    formal_import: bool,
    approval_token: str | None = None,
) -> None:
    if formal_import:
        if database_name != FORMAL_DATABASE:
            raise ImportSafetyError("formal import flag requires the formal energy_maintenance database")
        _assert_formal_approval_token(approval_token)
        _assert_formal_gates()
        return
    if database_name != TEST_DATABASE:
        raise ImportSafetyError(f"test import writes are allowed only in {TEST_DATABASE}")


def _assert_status_and_boolean_checks(
    section_name: str,
    payload: Mapping[str, object],
    *,
    expected_status: str,
    required_boolean_keys: Sequence[str],
) -> None:
    """Enforce a narrow formal-gate contract without accepting truthy values."""

    if not isinstance(payload, Mapping):
        raise ImportSafetyError(
            f"formal import gate failed: section={section_name}; "
            "missing_keys=[]; failed_keys=[]; invalid_type_keys=[payload]"
        )

    missing_keys = [key for key in ("status", *required_boolean_keys) if key not in payload]
    failed_keys: list[str] = []
    invalid_type_keys: list[str] = []

    if "status" in payload and payload["status"] != expected_status:
        failed_keys.append("status")

    for key in required_boolean_keys:
        if key not in payload:
            continue
        value = payload[key]
        if not isinstance(value, bool):
            invalid_type_keys.append(key)
        elif value is not True:
            failed_keys.append(key)

    if missing_keys or failed_keys or invalid_type_keys:
        raise ImportSafetyError(
            f"formal import gate failed: section={section_name}; "
            f"missing_keys={missing_keys}; failed_keys={failed_keys}; "
            f"invalid_type_keys={invalid_type_keys}"
        )


def _assert_formal_approval_token(approval_token: str | None) -> None:
    """Bind every formal Apply to the current frozen v3 plan and importer hash."""

    if not approval_token:
        raise ImportSafetyError("formal import requires an approval token")
    if not V3_FORMAL_PLAN_PATH.is_file():
        raise ImportSafetyError("formal import blocked: approved v3 formal import plan is missing")

    plan_sha256 = _hash_file(V3_FORMAL_PLAN_PATH)
    expected_token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{plan_sha256}"
    if approval_token != expected_token:
        raise ImportSafetyError("formal import blocked: approval token does not match the current v3 plan")

    plan = json.loads(V3_FORMAL_PLAN_PATH.read_text(encoding="utf-8"))
    importer = plan.get("importer") if isinstance(plan.get("importer"), Mapping) else {}
    safety = plan.get("safety") if isinstance(plan.get("safety"), Mapping) else {}
    totals = plan.get("totals") if isinstance(plan.get("totals"), Mapping) else {}
    classifications = plan.get("candidate_classifications")
    blocking_classifications = {
        "FORMAL_COMPARISON_NOT_EXECUTED",
        "ALREADY_PRESENT_METADATA_DIFFERENCE",
        "SAME_TITLE_DIFFERENT_HASH",
        "BLOCKED_INVALID_METADATA",
    }
    plan_valid = (
        plan.get("schema_version") == "3.0.0"
        and plan.get("task") == "Task 28A-R3A-R2"
        and plan.get("status") == "PREFLIGHT_V3_READY_AWAITING_APPROVAL"
        and importer.get("path") == "backend/scripts/import_competition_knowledge_corpus.py"
        and importer.get("new_sha256") == _hash_file(Path(__file__).resolve())
        and importer.get("gate_contract_version") == FORMAL_GATE_CONTRACT_VERSION
        and safety.get("formal_business_sql_writes") == 0
        and safety.get("formal_schema_changes") == 0
        and safety.get("formal_alembic_changes") == 0
        and safety.get("formal_import_executed") is False
        and safety.get("fresh_full_backup_created") is False
        and safety.get("fresh_full_backup_required_before_apply") is True
        and totals.get("selected_sungrow_documents") == 0
        and totals.get("selected_media_assets") == 0
        and totals.get("selected_user_cases") == 0
        and isinstance(classifications, list)
        and not any(
            isinstance(item, Mapping) and item.get("classification") in blocking_classifications
            for item in classifications
        )
    )
    if not plan_valid:
        raise ImportSafetyError("formal import blocked: current v3 plan safety contract is invalid")


def _assert_formal_gates(acceptance_path: Path | None = None) -> None:
    acceptance_path = acceptance_path or ACCEPTANCE_PATH
    if not acceptance_path.exists():
        raise ImportSafetyError("formal import blocked: Task 28A acceptance file does not exist")
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    test_database = acceptance.get("test_database") or {}
    knowledge = acceptance.get("knowledge_import") or {}
    qa = acceptance.get("qa_persistence") or {}
    _assert_status_and_boolean_checks(
        "qa_persistence",
        qa,
        expected_status="PASSED",
        required_boolean_keys=QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS,
    )
    required = {
        "test_database_created": test_database.get("created") is True,
        "alembic_head": test_database.get("alembic_head") == "20260712_0015",
        "parsed_documents": int(knowledge.get("parsed_documents") or 0) > 0,
    }
    failures = [name for name, passed in required.items() if not passed]
    if failures:
        raise ImportSafetyError(f"formal import gates failed: {', '.join(failures)}")


def _reviewer(db: Session) -> User:
    user = db.scalar(
        select(User)
        .where(User.role.in_(("admin", "expert")), User.is_active.is_(True), User.status == "active")
        .order_by(User.created_at.asc())
    )
    if not user:
        raise ImportSafetyError("an active admin or expert user is required for knowledge import")
    return user


def _quality_is_acceptable(document: Any) -> bool:
    metadata = document.metadata_json or {}
    return (
        document.parse_status == "parsed"
        and document.chunk_count > 0
        and not document.error_message
        and float(metadata.get("replacement_character_ratio") or 0.0) <= 0.01
    )


async def _import_documents(
    *,
    database_url: str,
    documents: list[dict[str, Any]],
    approve_huawei: bool,
    formal_import: bool,
    approval_token: str | None,
) -> list[dict[str, Any]]:
    database_name = _database_name(database_url)
    _assert_apply_database(database_name, formal_import, approval_token)
    if not formal_import:
        os.environ["UPLOAD_DIR"] = "storage/tmp/task28a_test_uploads"
        get_settings.cache_clear()

    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    results: list[dict[str, Any]] = []
    try:
        with session_factory() as db:
            connected_database = db.scalar(text("SELECT current_database()"))
            if connected_database != database_name:
                raise ImportSafetyError("connected database does not match the requested target")
            reviewer = _reviewer(db)
            repository = KnowledgeRepository(db)
            knowledge_service = KnowledgeService(db)
            review_service = ReviewService(db)

            for item in documents:
                existing = repository.get_document_by_source_sha256(item["sha256"])
                if existing:
                    results.append({
                        "status": "duplicate_skipped",
                        "relative_path": item["relative_path"],
                        "sha256": item["sha256"],
                        "document_id": str(existing.id),
                        "chunk_count": existing.chunk_count,
                        "review_status": existing.review_status,
                    })
                    continue

                source_path: Path = item["verified_source_path"]
                media_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
                try:
                    with source_path.open("rb") as file_handle:
                        upload = UploadFile(
                            file=file_handle,
                            filename=item["file_name"],
                            headers=Headers({"content-type": media_type}),
                        )
                        upload_result = await knowledge_service.upload_and_process_document(
                            file=upload,
                            title=item["title"],
                            manufacturer=item["manufacturer_normalized"],
                            product_series=item["product_family"],
                            device_type="pv_inverter",
                            document_type=item["document_type"],
                            description="Task 28A competition corpus import; review required before retrieval.",
                            source=f"task28a_sha256:{item['sha256']}",
                            current_user=reviewer,
                        )
                    document = upload_result["document"]
                    metadata = dict(document.metadata_json or {})
                    metadata.update({
                        "task28a_corpus_id": "competition_corpus_v1",
                        "task28a_source_sha256": item["sha256"],
                        "task28a_source_relative_path": item["relative_path"],
                        "task28a_alias_of_relative_path": item.get("alias_of_relative_path"),
                        "issuer": item["manufacturer"],
                        "product_family": item["product_family"],
                        "scope": item["scope"],
                        "language": item["language"],
                        "normalized_language": item["language"],
                        "source_provenance": "VENDOR_OFFICIAL",
                        "vendor_source_verified": True,
                        "content_parse_verified": document.parse_status == "parsed" and document.chunk_count > 0,
                        "quality_status": "READY_FOR_HUMAN_REVIEW",
                        "is_current_version": item["is_current_version"],
                        "is_formal_retrieval_candidate": item["is_formal_retrieval_candidate"],
                        "document_number": item.get("detected_document_number"),
                        "document_version": item.get("detected_document_version"),
                        "release_date": item.get("detected_release_date"),
                        "model_evidence_lines": item.get("model_evidence_lines") or [],
                        "replacement_character_ratio": item["parse_preflight"].get("replacement_character_ratio"),
                        "approved_for_pilot": False,
                        "automatic_approval": False,
                    })
                    document.source_type = item["source_type"]
                    document.metadata_json = metadata
                    document.review_status = "pending_review"
                    repository.update_document(document)
                    db.commit()

                    if not _quality_is_acceptable(document):
                        raise ImportSafetyError("parsed document failed post-import quality checks")
                    if approve_huawei and item["manufacturer_normalized"] == "huawei":
                        review_service.approve_document(
                            document.id,
                            comment="Task 28A source, hash, parser, chunks, and metadata verified.",
                            reviewer=reviewer,
                        )
                        db.refresh(document)

                    results.append({
                        "status": "imported",
                        "relative_path": item["relative_path"],
                        "sha256": item["sha256"],
                        "document_id": str(document.id),
                        "chunk_count": document.chunk_count,
                        "parse_status": document.parse_status,
                        "review_status": document.review_status,
                        "scope": (document.metadata_json or {}).get("scope"),
                    })
                except (KnowledgeServiceError, ReviewServiceError, ImportSafetyError, OSError) as exc:
                    db.rollback()
                    results.append({
                        "status": "failed",
                        "relative_path": item["relative_path"],
                        "sha256": item["sha256"],
                        "error": f"{type(exc).__name__}: {exc}",
                    })
    finally:
        engine.dispose()
    return results


def _summary(
    *,
    manifest: dict[str, Any],
    selected: list[dict[str, Any]],
    results: list[dict[str, Any]],
    mode: str,
    manufacturer: str,
    database_name: str | None,
) -> dict[str, Any]:
    imported = [item for item in results if item["status"] == "imported"]
    duplicate = [item for item in results if item["status"] == "duplicate_skipped"]
    failed = [item for item in results if item["status"] == "failed"]
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DRY_RUN_READY" if mode == "dry_run" else ("APPLY_COMPLETED" if not failed else "APPLY_WITH_FAILURES"),
        "mode": mode,
        "database": database_name,
        "manufacturer_filter": manufacturer,
        "manifest_documents": len(manifest["documents"]),
        "selected_documents": len(selected),
        "selected_huawei_documents": sum(x["manufacturer_normalized"] == "huawei" for x in selected),
        "selected_sungrow_documents": sum(x["manufacturer_normalized"] == "sungrow" for x in selected),
        "not_selected_for_automatic_import": len(manifest["documents"]) - len(selected),
        "imported_documents": len(imported),
        "duplicates_skipped": len(duplicate),
        "parsed_documents": sum(item.get("parse_status") == "parsed" for item in imported),
        "failed_documents": len(failed),
        "chunks": sum(int(item.get("chunk_count") or 0) for item in imported),
        "pending_documents": sum(item.get("review_status") == "pending_review" for item in imported),
        "approved_documents": sum(item.get("review_status") == "approved" for item in imported),
        "future_sungrow_scope_documents": sum(item.get("scope") == "future_sungrow_scope" for item in imported),
        "results": results,
        "secrets_printed": False,
        "vector_rebuild_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely import the Task 28A competition knowledge corpus")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--database-url", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--manufacturer", choices=("all", "huawei", "sungrow"), default="all")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--backup-evidence-path", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--backup-evidence-sha256", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--approve-huawei", action="store_true")
    parser.add_argument("--formal-import", action="store_true")
    parser.add_argument("--approval-token", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.formal_import and not args.apply:
        raise ImportSafetyError("--formal-import requires --apply")

    # These paths are checked before manifest parsing, database URL use, or any
    # possible engine creation. The original R3B Apply found a relative report
    # path only after importing documents; this order makes that impossible.
    report_path = _validate_report_path(args.report_path)
    manifest_path = _safe_project_path(args.manifest, label="manifest path", must_exist=True)
    source_root = _safe_project_path(args.source_root, label="source root path", must_exist=True)

    manifest, documents = _load_manifest(manifest_path, source_root)
    selected = _selected_documents(documents, args.manufacturer)
    max_upload_bytes = get_settings().MAX_UPLOAD_SIZE_MB * 1024 * 1024
    oversized = [item["relative_path"] for item in selected if int(item["size_bytes"]) > max_upload_bytes]
    if oversized:
        raise ImportSafetyError(f"selected documents exceed upload limit: {', '.join(oversized)}")
    database_url = args.database_url or os.getenv("DATABASE_URL", "").strip() or None
    database_name = _database_name(database_url) if database_url else None
    apply_mode = bool(args.apply)
    preflight: dict[str, str | None] = {}

    if not apply_mode:
        results = [{
            "status": "ready",
            "relative_path": item["relative_path"],
            "sha256": item["sha256"],
            "manufacturer": item["manufacturer_normalized"],
            "document_type": item["document_type"],
            "size_bytes": item["size_bytes"],
        } for item in selected]
    else:
        if not database_url:
            raise ImportSafetyError("--apply requires --database-url or DATABASE_URL")
        preflight = _validate_apply_preflight(
            args=args,
            database_url=database_url,
            selected=selected,
        )
        database_name = str(preflight["database_name"])
        results = asyncio.run(_import_documents(
            database_url=database_url,
            documents=selected,
            approve_huawei=args.approve_huawei,
            formal_import=args.formal_import,
            approval_token=args.approval_token,
        ))

    report = _summary(
        manifest=manifest,
        selected=selected,
        results=results,
        mode="apply" if apply_mode else "dry_run",
        manufacturer=args.manufacturer,
        database_name=database_name,
    )
    report["resume_requested"] = bool(args.resume)
    report["formal_import"] = bool(args.formal_import)
    report["huawei_approval_requested"] = bool(args.approve_huawei)
    if preflight.get("backup_evidence_path"):
        report["backup_evidence_path"] = preflight["backup_evidence_path"]
        report["backup_evidence_sha256"] = preflight["backup_evidence_sha256"]
    try:
        _atomic_json(report_path, report)
    except (ImportSafetyError, OSError) as exc:
        # A preflight probe makes this an exceptional disk/permission failure.
        # Do not retry an Apply: reconcile committed data before any next action.
        print(json.dumps({
            "status": "IMPORT_COMMITTED_REPORT_WRITE_FAILED" if apply_mode else "REPORT_WRITE_FAILED",
            "database": database_name,
            "error": f"{type(exc).__name__}: {exc}",
            "automatic_apply_retry": False,
            "required_next_step": "Run read-only reconciliation and idempotence checks; do not rerun Apply automatically.",
        }, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if report["failed_documents"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
