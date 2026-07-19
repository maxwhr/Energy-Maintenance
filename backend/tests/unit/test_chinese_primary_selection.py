from app.services.knowledge_language_policy_service import KnowledgeLanguagePolicyService


def test_chinese_is_primary_and_english_is_alternate():
    service = KnowledgeLanguagePolicyService()
    zh = service.policy_metadata(metadata={"language": "zh-CN"}, title="手册", content="中文安全说明" * 40)
    en = service.policy_metadata(metadata={"language": "en"}, title="Manual", content="English manual content " * 40)
    assert zh["is_default_retrieval_language"] is True
    assert zh["primary_language"] == "zh-CN"
    assert en["alternate_language"] == "en"
