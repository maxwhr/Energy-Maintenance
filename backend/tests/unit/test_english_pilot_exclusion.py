from app.services.knowledge_language_policy_service import KnowledgeLanguagePolicyService


def test_english_is_retained_but_excluded():
    metadata = KnowledgeLanguagePolicyService().policy_metadata(
        metadata={"language": "en"}, title="Manual", content="English content " * 40)
    assert metadata["translation_status"] == "original_vendor_language"
    assert metadata["is_default_retrieval_language"] is False
    assert metadata["is_pilot_eligible"] is False
