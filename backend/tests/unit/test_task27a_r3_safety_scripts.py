from __future__ import annotations

from types import SimpleNamespace

import pytest

from cleanup_task27a_production_qa_incident import extract_request_id
from provision_task27a_test_database import (
    assert_safe_role_name,
    assert_safe_test_database_name,
    build_create_database_sql,
)


def test_task27a_provision_allows_only_explicit_test_database_names() -> None:
    assert assert_safe_test_database_name("energy_maintenance_task27a_test") == "energy_maintenance_task27a_test"
    assert assert_safe_test_database_name("energy_maintenance_test") == "energy_maintenance_test"


@pytest.mark.parametrize(
    "database_name",
    ["energy_maintenance", "postgres", "template0", "template1", "unrelated", "task27a-test", 'task27a_test"x'],
)
def test_task27a_provision_rejects_formal_or_unsafe_database_names(database_name: str) -> None:
    with pytest.raises(ValueError):
        assert_safe_test_database_name(database_name)


def test_task27a_provision_generates_minimal_owner_sql() -> None:
    sql = build_create_database_sql("energy_maintenance_task27a_test", "energy_user")
    assert sql == (
        'CREATE DATABASE "energy_maintenance_task27a_test" OWNER "energy_user" '
        "ENCODING 'UTF8' TEMPLATE template0;"
    )
    assert "PASSWORD" not in sql


def test_task27a_provision_rejects_unsafe_owner() -> None:
    with pytest.raises(ValueError):
        assert_safe_role_name('energy_user" SUPERUSER')


def test_task27a_cleanup_extracts_request_id_only_from_diagnostics() -> None:
    record = SimpleNamespace(related_history=[
        {"record_type": "other"},
        {"record_type": "query_aware_retrieval_diagnostics", "request_id": "req_task27a"},
    ])
    assert extract_request_id(record) == "req_task27a"
