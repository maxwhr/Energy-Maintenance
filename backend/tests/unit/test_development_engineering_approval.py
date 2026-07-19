from unittest.mock import MagicMock

from app.models import KnowledgeDocument
from app.services.development_engineering_approval_service import DevelopmentEngineeringApprovalService


def test_development_approval_sets_pilot_flags_without_expert_claim():
    db = MagicMock()
    document = KnowledgeDocument(title="中文手册", manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="USER_MANUAL", parse_status="parsed", review_status="pending_review",
        status="active", metadata_json={"normalized_language": "zh-CN"})
    metrics = {"quality_score": 100, "exact_duplicate_ratio": 0, "locator_coverage": 1,
               "page_coverage": 1, "heading_coverage": 1}
    assert DevelopmentEngineeringApprovalService(db).approve(document, metrics=metrics, reason="passed", rule_version="v1")
    assert document.review_status == "approved"
    assert document.metadata_json["approved_for_pilot"] is True
    assert document.metadata_json["expert_verified"] is False
    assert document.metadata_json["second_reviewed"] is False
