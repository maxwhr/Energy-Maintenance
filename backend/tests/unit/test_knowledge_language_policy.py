from app.services.knowledge_language_policy_service import KnowledgeLanguagePolicyService


def test_language_aliases_and_content_ratio():
    service = KnowledgeLanguagePolicyService()
    assert service.normalize_language("zh_CN") == "zh-CN"
    assert service.normalize_language("English") == "en"
    result = service.assess(declared_language="zh", title="手册", content="安全操作步骤" * 30 + "SUN2000")
    assert result.normalized_language == "zh-CN"
    assert result.is_pilot_eligible is True


def test_title_alone_cannot_make_document_chinese():
    result = KnowledgeLanguagePolicyService().assess(
        declared_language=None, title="中文用户手册", content="English operating instructions " * 20)
    assert result.normalized_language == "en"
