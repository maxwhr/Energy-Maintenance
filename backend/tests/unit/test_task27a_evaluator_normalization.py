from __future__ import annotations

from scripts.check_task27a_huawei_rag_evaluation import _normalized_contains_point


def test_action_and_object_can_have_domain_context_between_them() -> None:
    assert _normalized_contains_point("检查并清理风扇上的异物。", "清理异物")


def test_installation_distance_accepts_interval_synonym_with_numeric_context() -> None:
    assert _normalized_contains_point("安装时顶部间距应不小于 500 mm。", "安装距离")


def test_minute_unit_is_normalized_without_changing_the_number() -> None:
    assert _normalized_contains_point("下电后等待15分钟再操作。", "等待15min")


def test_wrong_numeric_value_does_not_match() -> None:
    assert not _normalized_contains_point("下电后等待5分钟再操作。", "等待15min")


def test_unrelated_cleaning_action_does_not_match_foreign_object_removal() -> None:
    assert not _normalized_contains_point("清理散热器表面的积尘。", "清理异物")
