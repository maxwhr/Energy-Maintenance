from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest

import import_competition_knowledge_corpus as importer
from import_competition_knowledge_corpus import (
    FORMAL_GATE_CONTRACT_VERSION,
    ImportSafetyError,
    _load_manifest,
    _selected_documents,
    _validate_formal_candidate_scope,
    _validate_report_path,
)


@pytest.fixture
def project_temp_dir() -> Path:
    path = importer.PROJECT_ROOT / ".runtime" / "task28a-r3c" / "pytest" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _forbid_database_engine(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"count": 0}

    def fail_engine(*_args: object, **_kwargs: object) -> object:
        calls["count"] += 1
        pytest.fail("preflight failure must not create a database engine")

    monkeypatch.setattr(importer, "create_engine", fail_engine)
    return calls


def _formal_argv(report_path: Path, *, token: str = "invalid-token") -> list[str]:
    return [
        "import_competition_knowledge_corpus.py",
        "--apply",
        "--formal-import",
        "--manufacturer",
        "huawei",
        "--approve-huawei",
        "--database-url",
        "postgresql+psycopg://energy_user:placeholder@127.0.0.1:55432/energy_maintenance",
        "--approval-token",
        token,
        "--report-path",
        str(report_path),
    ]


@pytest.mark.parametrize(
    "invalid_report",
    [
        Path("relative-report.json"),
        importer.PROJECT_ROOT.parent / "Energy-Maintenance-escape" / "report.json",
        importer.PROJECT_ROOT / ".runtime" / "task28a-r3c" / "safe" / ".." / "escape.json",
    ],
)
def test_invalid_report_paths_are_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
    invalid_report: Path,
) -> None:
    calls = _forbid_database_engine(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_competition_knowledge_corpus.py",
            "--apply",
            "--database-url",
            "postgresql+psycopg://test_user:placeholder@127.0.0.1:55433/energy_maintenance_task27a_test",
            "--report-path",
            str(invalid_report),
        ],
    )

    with pytest.raises(ImportSafetyError, match="report path"):
        importer.main()
    assert calls["count"] == 0


def test_symlink_report_escape_is_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
    project_temp_dir: Path,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = project_temp_dir / "junction-like-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("the current Windows test environment does not permit symlink creation")

    calls = _forbid_database_engine(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_competition_knowledge_corpus.py",
            "--apply",
            "--database-url",
            "postgresql+psycopg://test_user:placeholder@127.0.0.1:55433/energy_maintenance_task27a_test",
            "--report-path",
            str(link / "report.json"),
        ],
    )

    with pytest.raises(ImportSafetyError, match="report path"):
        importer.main()
    assert calls["count"] == 0


def test_valid_project_absolute_report_path_passes_precheck(project_temp_dir: Path) -> None:
    report_path = project_temp_dir / "reports" / "result.json"
    assert _validate_report_path(report_path) == report_path.resolve()
    assert report_path.parent.is_dir()
    assert not list(report_path.parent.glob("*.preflight"))


def test_wrong_v3_token_is_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
    project_temp_dir: Path,
) -> None:
    calls = _forbid_database_engine(monkeypatch)
    monkeypatch.setattr(sys, "argv", _formal_argv(project_temp_dir / "wrong-token.json"))

    with pytest.raises(ImportSafetyError, match="approval token"):
        importer.main()
    assert calls["count"] == 0


def _valid_plan_payload() -> dict[str, object]:
    return {
        "schema_version": "3.0.0",
        "task": "Task 28A-R3A-R2",
        "status": "PREFLIGHT_V3_READY_AWAITING_APPROVAL",
        "importer": {
            "path": "backend/scripts/import_competition_knowledge_corpus.py",
            "new_sha256": hashlib.sha256(Path(importer.__file__).read_bytes()).hexdigest(),
            "gate_contract_version": FORMAL_GATE_CONTRACT_VERSION,
        },
        "safety": {
            "formal_business_sql_writes": 0,
            "formal_schema_changes": 0,
            "formal_alembic_changes": 0,
            "formal_import_executed": False,
            "fresh_full_backup_created": False,
            "fresh_full_backup_required_before_apply": True,
        },
        "totals": {
            "selected_sungrow_documents": 0,
            "selected_media_assets": 0,
            "selected_user_cases": 0,
        },
        "candidate_classifications": [{"classification": "NEW_IMPORT_CANDIDATE", "source_sha256": "placeholder"}],
    }


def test_plan_hash_mismatch_is_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
    project_temp_dir: Path,
) -> None:
    plan = _valid_plan_payload()
    plan["importer"]["new_sha256"] = "0" * 64  # type: ignore[index]
    plan_path = project_temp_dir / "invalid-importer-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}"
    calls = _forbid_database_engine(monkeypatch)
    monkeypatch.setattr(importer, "V3_FORMAL_PLAN_PATH", plan_path)
    monkeypatch.setattr(sys, "argv", _formal_argv(project_temp_dir / "plan-mismatch.json", token=token))

    with pytest.raises(ImportSafetyError, match="safety contract is invalid"):
        importer.main()
    assert calls["count"] == 0


def test_acceptance_gate_failure_is_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
    project_temp_dir: Path,
) -> None:
    plan_path = project_temp_dir / "valid-plan.json"
    plan_path.write_text(json.dumps(_valid_plan_payload()), encoding="utf-8")
    acceptance = json.loads(importer.ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    acceptance["qa_persistence"]["status"] = "FAILED"
    acceptance_path = project_temp_dir / "failed-acceptance.json"
    acceptance_path.write_text(json.dumps(acceptance), encoding="utf-8")
    token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}"
    calls = _forbid_database_engine(monkeypatch)
    monkeypatch.setattr(importer, "V3_FORMAL_PLAN_PATH", plan_path)
    monkeypatch.setattr(importer, "ACCEPTANCE_PATH", acceptance_path)
    monkeypatch.setattr(sys, "argv", _formal_argv(project_temp_dir / "failed-acceptance-report.json", token=token))

    with pytest.raises(ImportSafetyError, match="section=qa_persistence"):
        importer.main()
    assert calls["count"] == 0


def test_invalid_backup_evidence_is_rejected_before_database_connection(
    monkeypatch: pytest.MonkeyPatch,
    project_temp_dir: Path,
) -> None:
    plan_path = project_temp_dir / "valid-plan.json"
    plan_path.write_text(json.dumps(_valid_plan_payload()), encoding="utf-8")
    invalid_backup = project_temp_dir / "not-a-backup.txt"
    invalid_backup.write_text("not a pg_dump archive", encoding="utf-8")
    token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}"
    calls = _forbid_database_engine(monkeypatch)
    monkeypatch.setattr(importer, "V3_FORMAL_PLAN_PATH", plan_path)
    argv = _formal_argv(project_temp_dir / "invalid-backup-report.json", token=token)
    argv.extend(["--backup-evidence-path", str(invalid_backup), "--backup-evidence-sha256", hashlib.sha256(invalid_backup.read_bytes()).hexdigest()])
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(ImportSafetyError, match="backup evidence path"):
        importer.main()
    assert calls["count"] == 0


def test_formal_candidate_scope_rejects_sungrow_without_database_connection() -> None:
    _manifest, documents = _load_manifest(importer.DEFAULT_MANIFEST, importer.DEFAULT_SOURCE_ROOT)
    selected = _selected_documents(documents, "huawei")
    _validate_formal_candidate_scope(selected)
    altered = [*selected, {**selected[0], "manufacturer_normalized": "sungrow"}]
    with pytest.raises(ImportSafetyError, match="candidates do not exactly match|non-Huawei"):
        _validate_formal_candidate_scope(altered)


def test_post_commit_report_failure_never_retries_apply(
    monkeypatch: pytest.MonkeyPatch,
    project_temp_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = {"apply": 0}

    async def fake_import(**_kwargs: object) -> list[dict[str, object]]:
        calls["apply"] += 1
        return [{"status": "imported", "chunk_count": 1, "parse_status": "parsed", "review_status": "approved"}]

    def fail_report(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated full disk")

    monkeypatch.setattr(importer, "_import_documents", fake_import)
    monkeypatch.setattr(importer, "_atomic_json", fail_report)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_competition_knowledge_corpus.py",
            "--apply",
            "--manufacturer",
            "huawei",
            "--database-url",
            "postgresql+psycopg://test_user:placeholder@127.0.0.1:55433/energy_maintenance_task27a_test",
            "--report-path",
            str(project_temp_dir / "post-commit-report.json"),
        ],
    )

    assert importer.main() == 2
    assert calls["apply"] == 1
    assert "IMPORT_COMMITTED_REPORT_WRITE_FAILED" in capsys.readouterr().out
