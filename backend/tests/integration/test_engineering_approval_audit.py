from unittest.mock import MagicMock

from app.models import KnowledgeDocument, KnowledgeReviewRecord, OperationLog
from app.services.development_engineering_approval_service import DevelopmentEngineeringApprovalService


def test_engineering_approval_writes_both_review_and_operation_audits():
    db = MagicMock()
    document = KnowledgeDocument(title="中文 FAQ", manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="FAQ_TROUBLESHOOTING", parse_status="parsed",
        review_status="pending_review", status="active", metadata_json={"normalized_language": "zh-CN"})
    metrics = {"quality_score": 100, "exact_duplicate_ratio": 0, "locator_coverage": 1,
               "page_coverage": 0, "heading_coverage": 1}
    DevelopmentEngineeringApprovalService(db).approve(document, metrics=metrics, reason="passed", rule_version="v1")
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(item, KnowledgeReviewRecord) for item in added)
    assert any(isinstance(item, OperationLog) for item in added)
