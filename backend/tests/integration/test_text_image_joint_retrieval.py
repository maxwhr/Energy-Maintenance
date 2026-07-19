from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User
from app.services.cross_modal_retrieval_plan_service import CrossModalRetrievalPlanService
from app.services.cross_modal_retrieval_service import CrossModalRetrievalService
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution


def test_cross_modal_retrieval_uses_deterministic_channels_without_qwen3() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        assert user is not None
        plan = CrossModalRetrievalPlanService().build(
            original_query="SUN2000 告警代码 2064 的原因和处理建议是什么",
            normalized_query=None,
            confirmed_facts={},
            resolution=MultimodalEntityResolution(
                resolved_device_model="SUN2000",
                resolved_product_family="SUN2000",
                resolved_equipment_category="pv_inverter",
                resolved_alarm_codes=["2064"],
                resolution_confidence=1.0,
            ),
            evidence_items=[],
            occurrence_conditions=[],
            requested_information=["CAUSE", "ACTION", "SAFETY"],
        )

        result = CrossModalRetrievalService(db, current_user=user).retrieve(plan, top_k=5)

        assert result.generated_queries[0]["query_type"] == "ORIGINAL_TEXT"
        assert set(result.requested_channels) == {"EXACT_KEYWORD", "SCOPED_KEYWORD", "KG_ALIAS"}
        assert result.dedicated_rerank["status"] == "DEFERRED_QWEN3_RERANK_CONFIG"
        assert result.dedicated_rerank["used"] is False
        assert result.external_call_counts == {
            "embedding": 0,
            "dashvector": 0,
            "qwen3_rerank": 0,
            "cloud_llm": 0,
        }
        assert all(item["scope_validation_passed"] for item in result.surfaced_results)


def test_cross_modal_retrieval_abstains_for_unsupported_confirmed_device_model() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        assert user is not None
        plan = CrossModalRetrievalPlanService().build(
            original_query="不存在的 ZXQ-9999 设备告警 999999，请给出该型号专属维修参数",
            normalized_query=None,
            confirmed_facts={},
            resolution=MultimodalEntityResolution(
                resolved_device_model="ZXQ-9999",
                resolved_product_family=None,
                resolved_alarm_codes=["999999"],
                resolution_confidence=1.0,
            ),
            evidence_items=[],
            occurrence_conditions=[],
            requested_information=["CAUSE", "ACTION", "SAFETY"],
        )

        result = CrossModalRetrievalService(db, current_user=user).retrieve(plan, top_k=5)

        assert result.confidence_status == "INSUFFICIENT_EVIDENCE"
        assert result.actual_channels == []
        assert result.raw_candidates == []
        assert result.surfaced_results == []
        assert result.citations == []
        assert result.deterministic_rerank["reason"] == "UNSUPPORTED_DEVICE_MODEL_SCOPE"
        assert result.external_call_counts == {
            "embedding": 0,
            "dashvector": 0,
            "qwen3_rerank": 0,
            "cloud_llm": 0,
        }
