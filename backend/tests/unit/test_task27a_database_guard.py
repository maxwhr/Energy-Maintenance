import pytest

from check_task27a_qa_persistence_flow import assert_test_database_name


def test_task27a_database_guard_allows_only_explicit_test_names() -> None:
    assert assert_test_database_name("energy_maintenance_task27a_test") == "energy_maintenance_task27a_test"
    assert assert_test_database_name("energy_maintenance_test") == "energy_maintenance_test"


@pytest.mark.parametrize("database_name", ["energy_maintenance", "postgres", "", None])
def test_task27a_database_guard_rejects_non_test_databases(database_name) -> None:
    with pytest.raises(RuntimeError, match="database name"):
        assert_test_database_name(database_name)
