from __future__ import annotations

from types import SimpleNamespace

from app.services.cross_modal_retrieval_plan_service import CrossModalRetrievalPlanService
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution


def test_plan_retains_original_and_uses_only_evidence_signals() -> None:
    evidence = [SimpleNamespace(
        evidence_id="visual-1",
        observation_status="INFERRED",
        modality="VISUAL_REGION",
        evidence_type="INDICATOR_LIGHT",
        indicator_state_candidates=["red blinking"],
        component_candidates=[],
        symptom_candidates=[],
        normalized_text="红色指示灯闪烁候选",
    )]
    resolution = MultimodalEntityResolution(
        resolved_device_model="SUN2000-100KTL-M2",
        resolved_product_family="SUN2000",
        resolved_alarm_codes=[],
        resolved_conditions=["夜间"],
    )

    plan = CrossModalRetrievalPlanService().build(
        original_query="晚上设备连不上，图片里红灯闪烁。",
        normalized_query=None,
        confirmed_facts={},
        resolution=resolution,
        evidence_items=evidence,
        occurrence_conditions=["夜间"],
    )

    assert plan.queries[0].query_type == "ORIGINAL_TEXT"
    assert plan.queries[0].query == "晚上设备连不上，图片里红灯闪烁。"
    assert len(plan.queries) <= 5
    assert any(item.query_type == "VISUAL_SYMPTOM_QUERY" and "red blinking" in item.query for item in plan.queries)
    assert plan.dedicated_rerank_status == "DEFERRED_QWEN3_RERANK_CONFIG"
    assert plan.resolved_device_model == "SUN2000-100KTL-M2"
    assert plan.resolved_product_family == "SUN2000"
    assert plan.resolved_alarm_codes == []
    assert all("2064" not in item.query for item in plan.queries)
