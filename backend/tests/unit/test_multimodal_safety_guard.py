from __future__ import annotations

from types import SimpleNamespace

from app.services.multimodal_safety_guard_service import MultimodalSafetyGuardService


def _evidence(text: str):
    return SimpleNamespace(
        observation_status="OBSERVED",
        observed_text=text,
        normalized_text=text,
        symptom_candidates=[],
    )


def test_severe_visual_risk_blocks_normal_actions() -> None:
    result = MultimodalSafetyGuardService().evaluate(
        evidence_items=[_evidence("设备表面可见烧蚀并冒烟")],
        proposed_actions=["继续复位设备", "停止操作并隔离现场"],
        valid_safety_citations=[],
    )

    assert result.safety_level == "CRITICAL"
    assert result.stop_required is True
    assert "继续复位设备" in result.blocked_actions
    assert "停止操作并隔离现场" in result.allowed_actions


def test_dangerous_action_requires_safe_state_and_official_source() -> None:
    result = MultimodalSafetyGuardService().evaluate(
        evidence_items=[_evidence("直流侧异常")],
        proposed_actions=["开盖检查内部接线"],
        valid_safety_citations=[],
        device_state_confirmed_safe=False,
    )

    assert result.allowed_actions == []
    assert result.blocked_actions == ["开盖检查内部接线"]
