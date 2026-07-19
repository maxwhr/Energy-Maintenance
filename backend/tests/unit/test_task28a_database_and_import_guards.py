from __future__ import annotations

import sys

import pytest

import import_competition_knowledge_corpus as importer
from import_competition_knowledge_corpus import (
    DEFAULT_MANIFEST,
    DEFAULT_SOURCE_ROOT,
    FORMAL_DATABASE,
    TEST_DATABASE,
    ImportSafetyError,
    _assert_apply_database,
    _load_manifest,
    _selected_documents,
)
from provision_task28a_test_database import (
    DEFAULT_SQL_PATH,
    TEST_ROLE,
    assert_test_identifiers,
)


def test_provisioning_scope_accepts_only_designated_role_and_database() -> None:
    assert assert_test_identifiers(TEST_ROLE, TEST_DATABASE) == (TEST_ROLE, TEST_DATABASE)
    with pytest.raises(ValueError):
        assert_test_identifiers("energy_user", TEST_DATABASE)
    with pytest.raises(ValueError):
        assert_test_identifiers(TEST_ROLE, FORMAL_DATABASE)


def test_import_apply_guard_rejects_formal_database_without_formal_mode() -> None:
    _assert_apply_database(TEST_DATABASE, formal_import=False)
    with pytest.raises(ImportSafetyError):
        _assert_apply_database(FORMAL_DATABASE, formal_import=False)
    with pytest.raises(ImportSafetyError):
        _assert_apply_database("postgres", formal_import=False)


def test_import_manifest_selection_is_review_gated() -> None:
    manifest, documents = _load_manifest(DEFAULT_MANIFEST, DEFAULT_SOURCE_ROOT)
    selected = _selected_documents(documents, "all")
    assert len(manifest["documents"]) == 21
    assert len(selected) == 15
    assert sum(item["manufacturer_normalized"] == "huawei" for item in selected) == 10
    assert sum(item["manufacturer_normalized"] == "sungrow" for item in selected) == 5
    assert all(item["document_type"] != "unknown_review_required" for item in selected)
    assert all(item["alias_of_relative_path"] is None for item in selected)


def test_manual_provisioning_sql_contains_no_real_secret() -> None:
    content = DEFAULT_SQL_PATH.read_text(encoding="utf-8")
    assert "<SECURE_RANDOM_PASSWORD>" in content
    assert "energy_password" not in content
    assert TEST_ROLE in content
    assert TEST_DATABASE in content
    assert "SUPERUSER" in content and "NOSUPERUSER" in content
    assert "NOCREATEDB" in content
    assert "NOCREATEROLE" in content


def test_dry_run_never_creates_a_database_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_engine(*_args: object, **_kwargs: object) -> object:
        pytest.fail("dry-run must not create a database engine")

    monkeypatch.setattr(importer, "create_engine", fail_engine)
    monkeypatch.setattr(importer, "_atomic_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["import_competition_knowledge_corpus.py", "--dry-run", "--manufacturer", "huawei"],
    )

    assert importer.main() == 0
