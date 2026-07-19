from unittest.mock import Mock

from app.schemas.retrieval import RetrievalQueryRequest
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.retrieval_service import RetrievalService


def test_retrieval_query_defaults_preserve_writes_but_disable_external_paths() -> None:
    payload = RetrievalQueryRequest(query="SUN2000 告警排查")

    assert payload.persist_result is True
    assert payload.enable_llm is False
    assert payload.allow_real_api is False
    assert payload.enable_vector is False


def test_preview_query_skips_qa_persistence() -> None:
    service = RetrievalService.__new__(RetrievalService)
    service._save_qa_record = Mock()
    payload = RetrievalQueryRequest(query="预览查询", persist_result=False)

    persisted = service._persist_qa_if_requested(Mock(), payload, Mock(), [])

    assert persisted is False
    service._save_qa_record.assert_not_called()


def test_normal_query_keeps_qa_persistence() -> None:
    service = RetrievalService.__new__(RetrievalService)
    service._save_qa_record = Mock()
    payload = RetrievalQueryRequest(query="正式查询", persist_result=True)
    response = Mock()
    user = Mock()

    persisted = service._persist_qa_if_requested(response, payload, user, [])

    assert persisted is True
    service._save_qa_record.assert_called_once_with(response, payload, user, [])


def test_model_enhancement_requires_all_real_call_gates() -> None:
    service = RetrievalService.__new__(RetrievalService)
    payload = RetrievalQueryRequest(
        query="绝缘阻抗排查",
        enable_model_enhancement=True,
        enable_llm=True,
        allow_real_api=False,
    )

    service._apply_model_enhancement(Mock(), payload, Mock())


def test_safety_inquiry_is_not_misclassified_as_unsafe_execution() -> None:
    reason = QuerySignalExtractionService.unsafe_request_reason(
        "华为 SUN2000 能否带电拆装线缆，作业时需要哪些防护？"
    )

    assert reason is None


def test_explicit_live_work_instruction_remains_blocked() -> None:
    reason = QuerySignalExtractionService.unsafe_request_reason(
        "如何带电拆装 SUN2000 线缆"
    )

    assert reason == "unsafe_live_electrical_operation"
