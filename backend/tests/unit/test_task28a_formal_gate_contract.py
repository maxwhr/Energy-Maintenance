from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from import_competition_knowledge_corpus import (
    ACCEPTANCE_PATH,
    FORMAL_DATABASE,
    FORMAL_GATE_CONTRACT_VERSION,
    QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS,
    ImportSafetyError,
    _assert_apply_database,
    _assert_formal_approval_token,
    _assert_formal_gates,
    _assert_status_and_boolean_checks,
)
import import_competition_knowledge_corpus as importer


def _current_acceptance() -> dict[str, object]:
    return json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))


def _write_acceptance(path: Path, acceptance: dict[str, object]) -> None:
    path.write_text(json.dumps(acceptance, ensure_ascii=False), encoding="utf-8")


def _valid_qa_payload() -> dict[str, object]:
    return {"status": "PASSED", **{key: True for key in QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS}}


def _valid_v3_plan() -> dict[str, object]:
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
        "candidate_classifications": [{"classification": "NEW_IMPORT_CANDIDATE"}],
    }


def test_current_acceptance_passes_strict_qa_contract_without_database_connection() -> None:
    _assert_formal_gates()


def test_qa_contract_allows_extra_metadata_but_requires_every_fixed_check() -> None:
    payload = _valid_qa_payload() | {"audit_note": "extra metadata is allowed", "run_id": "r3-r2"}
    _assert_status_and_boolean_checks(
        "qa_persistence",
        payload,
        expected_status="PASSED",
        required_boolean_keys=QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS,
    )


@pytest.mark.parametrize(
    ("mutation", "error_fragment"),
    [
        (lambda payload: payload.pop("status"), "missing_keys=['status']"),
        (lambda payload: payload.__setitem__("status", "FAILED"), "failed_keys=['status']"),
        (lambda payload: payload.__setitem__("status", True), "failed_keys=['status']"),
        (lambda payload: payload.pop("trace_unique"), "missing_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", False), "failed_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", "true"), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", "True"), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", "PASSED"), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", 0), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", 1), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", None), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", []), "invalid_type_keys=['trace_unique']"),
        (lambda payload: payload.__setitem__("trace_unique", {}), "invalid_type_keys=['trace_unique']"),
    ],
)
def test_qa_contract_rejects_missing_failed_and_pseudo_boolean_values(
    mutation: object,
    error_fragment: str,
) -> None:
    payload = _valid_qa_payload()
    mutation(payload)  # type: ignore[operator]
    with pytest.raises(ImportSafetyError, match="section=qa_persistence") as exc_info:
        _assert_status_and_boolean_checks(
            "qa_persistence",
            payload,
            expected_status="PASSED",
            required_boolean_keys=QA_PERSISTENCE_REQUIRED_BOOLEAN_KEYS,
        )
    assert error_fragment in str(exc_info.value)


def test_historical_blocked_acceptance_is_rejected_without_connecting_to_postgresql(tmp_path: Path) -> None:
    blocked = copy.deepcopy(_current_acceptance())
    blocked["qa_persistence"]["status"] = "FAILED"  # type: ignore[index]
    path = tmp_path / "historical_blocked_acceptance.json"
    _write_acceptance(path, blocked)

    with pytest.raises(ImportSafetyError, match="section=qa_persistence"):
        _assert_formal_gates(path)


def test_formal_apply_rejects_missing_approval_token_before_any_database_connection() -> None:
    with pytest.raises(ImportSafetyError, match="requires an approval token"):
        _assert_apply_database(FORMAL_DATABASE, formal_import=True)


def test_formal_apply_cli_rejects_missing_approval_token_before_any_database_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_competition_knowledge_corpus.py",
            "--apply",
            "--formal-import",
            "--manufacturer",
            "huawei",
            "--approve-huawei",
            "--database-url",
            "postgresql+psycopg://energy_user:placeholder@127.0.0.1:55432/energy_maintenance",
        ],
    )
    with pytest.raises(ImportSafetyError, match="requires an approval token"):
        importer.main()


@pytest.mark.parametrize(
    ("mutation", "token_mode"),
    [
        (lambda plan: plan.__setitem__("schema_version", "1.0.0"), "current"),
        (lambda plan: plan["importer"].__setitem__("new_sha256", "0" * 64), "current"),  # type: ignore[index]
        (lambda plan: plan["candidate_classifications"].append({"classification": "FORMAL_COMPARISON_NOT_EXECUTED"}), "current"),  # type: ignore[index]
        (lambda plan: plan["candidate_classifications"].append({"classification": "ALREADY_PRESENT_METADATA_DIFFERENCE"}), "current"),  # type: ignore[index]
        (lambda plan: plan["candidate_classifications"].append({"classification": "SAME_TITLE_DIFFERENT_HASH"}), "current"),  # type: ignore[index]
        (lambda plan: plan["candidate_classifications"].append({"classification": "BLOCKED_INVALID_METADATA"}), "current"),  # type: ignore[index]
        (lambda plan: plan["totals"].__setitem__("selected_sungrow_documents", 1), "current"),  # type: ignore[index]
        (lambda plan: plan["totals"].__setitem__("selected_media_assets", 1), "current"),  # type: ignore[index]
        (lambda plan: plan["totals"].__setitem__("selected_user_cases", 1), "current"),  # type: ignore[index]
        (lambda plan: None, "v2"),
    ],
)
def test_formal_plan_and_token_mismatches_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: object,
    token_mode: str,
) -> None:
    plan = _valid_v3_plan()
    mutation(plan)  # type: ignore[operator]
    plan_path = tmp_path / "formal_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(importer, "V3_FORMAL_PLAN_PATH", plan_path)

    current_token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}"
    v2_token = "APPROVE_TASK28A_R3_FORMAL_IMPORT:200d21ed461ebd9c22d8adbb966b1504ff6ec8714efa4005ef6d0c772bfa0a20"
    with pytest.raises(ImportSafetyError):
        _assert_formal_approval_token(v2_token if token_mode == "v2" else current_token)


def test_historical_v1_blocked_plan_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    v1_plan = ACCEPTANCE_PATH.parent / "task28a_r3_formal_import_plan.json"
    monkeypatch.setattr(importer, "V3_FORMAL_PLAN_PATH", v1_plan)
    token = f"APPROVE_TASK28A_R3_FORMAL_IMPORT:{hashlib.sha256(v1_plan.read_bytes()).hexdigest()}"
    with pytest.raises(ImportSafetyError, match="safety contract is invalid"):
        _assert_formal_approval_token(token)
