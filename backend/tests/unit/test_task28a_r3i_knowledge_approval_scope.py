from types import SimpleNamespace
from uuid import uuid4

from app.services.knowledge_language_policy_service import KnowledgeLanguagePolicyService
from app.services.review_service import ReviewService


def test_chinese_upload_language_metadata_is_scope_ready() -> None:
    metadata = KnowledgeLanguagePolicyService().policy_metadata(
        metadata={"mime_type": "text/plain"},
        title="SUN2000 绝缘阻抗检修规程",
        content="绝缘阻抗告警排查、断电验电、组串检查和复检归档。" * 20,
    )

    assert metadata["normalized_language"] == "zh-CN"
    assert metadata["is_default_retrieval_language"] is True


def test_human_approved_user_upload_receives_competition_scope_metadata() -> None:
    reviewer = SimpleNamespace(id=uuid4())
    document = SimpleNamespace(
        source_type="user_upload",
        metadata_json={"normalized_language": "zh-CN"},
    )

    metadata = ReviewService._approval_metadata(document, reviewer)

    assert metadata["human_expert_approved"] is True
    assert metadata["competition_approved"] is True
    assert metadata["approval_mode"] == "human_expert_approval"
    assert metadata["human_expert_approved_by"] == str(reviewer.id)
