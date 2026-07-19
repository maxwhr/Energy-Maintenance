from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.schemas.query_aware_retrieval import QueryAwareSearchRequest, QueryAwareSearchResponse
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.query_signal_extraction_service import QuerySignalExtractionService


class _FakeSession:
    def __init__(self, *, fail_commit: bool = False):
        self.fail_commit = fail_commit
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise SQLAlchemyError("forced commit failure")

    def rollback(self):
        self.rollbacks += 1


class _FakeRepository:
    def __init__(self, existing_sequence=None, *, raise_integrity: bool = False):
        self.existing_sequence = list(existing_sequence or [])
        self.raise_integrity = raise_integrity
        self.created = []

    def get_by_trace_id(self, _trace_id):
        return self.existing_sequence.pop(0) if self.existing_sequence else None

    def create_qa_record(self, record):
        if self.raise_integrity:
            raise IntegrityError("insert qa_records", {}, RuntimeError("duplicate trace"))
        record.id = uuid4()
        self.created.append(record)
        return record


def _response(*, request_id: str = "task27a-request-1") -> QueryAwareSearchResponse:
    return QueryAwareSearchResponse(
        request_id=request_id,
        original_query="华为 SUN2000 绝缘阻抗低如何排查",
        normalized_query="华为 SUN2000 绝缘阻抗低如何排查",
        canonical_question="华为 SUN2000 绝缘阻抗低如何排查",
        primary_intent="TROUBLESHOOTING",
        confidence_status="GROUNDED",
        trace_id="qa_req_task27a_trace",
        answer="基于正式知识资料给出初步排查建议。",
        suggested_steps=["执行安全确认"],
        safety_notes=["断电并验电后操作"],
        confidence=0.72,
        query_signals={"manufacturer": "huawei", "product_family": "SUN2000"},
        retrieval_diagnostics={"scope_id": "huawei_sun2000_competition_v1"},
    )


def _service(session, repository, *, user_id=None):
    service = object.__new__(QueryAwareRetrievalService)
    service.db = session
    service.qa_repository = repository
    service.current_user = SimpleNamespace(id=user_id or uuid4())
    service.scope = SimpleNamespace(scope_id="huawei_sun2000_competition_v1")
    return service


def test_query_aware_request_persists_by_default() -> None:
    assert QueryAwareSearchRequest(query="SUN2000 告警").persist_result is True


def test_trace_is_deterministic_for_same_user_and_request_and_unique_otherwise() -> None:
    user_id = uuid4()
    service = _service(_FakeSession(), _FakeRepository(), user_id=user_id)
    assert service._trace_id("same-request") == service._trace_id("same-request")
    assert service._trace_id("same-request") != service._trace_id("other-request")
    other_service = _service(_FakeSession(), _FakeRepository())
    assert service._trace_id("same-request") != other_service._trace_id("same-request")


def test_persist_false_performs_zero_repository_or_session_writes() -> None:
    session = _FakeSession()
    repository = _FakeRepository()
    service = _service(session, repository)
    response = _response()
    service._persist_qa_record(
        response,
        QueryAwareSearchRequest(query=response.original_query, persist_result=False),
        QuerySignalExtractionService().extract(response.original_query),
    )
    assert response.persistence_status == "skipped_preview"
    assert repository.created == []
    assert session.commits == 0
    assert session.rollbacks == 0


def test_successful_persistence_records_request_signals_and_scope_once() -> None:
    session = _FakeSession()
    repository = _FakeRepository()
    service = _service(session, repository)
    response = _response()
    payload = QueryAwareSearchRequest(
        query=response.original_query,
        request_id=response.request_id,
    )
    service._persist_qa_record(
        response,
        payload,
        QuerySignalExtractionService().extract(response.original_query),
    )
    assert response.persistence_status == "persisted"
    assert response.qa_record_id
    assert len(repository.created) == 1
    assert session.commits == 1
    diagnostic = repository.created[0].related_history[0]
    assert diagnostic["request_id"] == response.request_id
    assert diagnostic["scope_id"] == "huawei_sun2000_competition_v1"
    assert diagnostic["query_signals"]["manufacturer"] == "huawei"


def test_existing_trace_reuses_exactly_one_idempotent_record() -> None:
    existing = SimpleNamespace(id=uuid4(), question="华为 SUN2000 绝缘阻抗低如何排查")
    session = _FakeSession()
    repository = _FakeRepository([existing])
    service = _service(session, repository)
    response = _response()
    service._persist_qa_record(
        response,
        QueryAwareSearchRequest(query=response.original_query, request_id=response.request_id),
        QuerySignalExtractionService().extract(response.original_query),
    )
    assert response.persistence_status == "reused_idempotent_record"
    assert response.qa_record_id == str(existing.id)
    assert repository.created == []
    assert session.commits == 0


def test_concurrent_unique_conflict_rolls_back_and_reuses_committed_record() -> None:
    existing = SimpleNamespace(id=uuid4(), question="华为 SUN2000 绝缘阻抗低如何排查")
    session = _FakeSession()
    repository = _FakeRepository([None, existing], raise_integrity=True)
    service = _service(session, repository)
    response = _response()
    service._persist_qa_record(
        response,
        QueryAwareSearchRequest(query=response.original_query, request_id=response.request_id),
        QuerySignalExtractionService().extract(response.original_query),
    )
    assert session.rollbacks == 1
    assert response.persistence_status == "reused_idempotent_record"
    assert response.qa_record_id == str(existing.id)


def test_commit_failure_rolls_back_and_never_claims_saved() -> None:
    session = _FakeSession(fail_commit=True)
    repository = _FakeRepository()
    service = _service(session, repository)
    response = _response()
    service._persist_qa_record(
        response,
        QueryAwareSearchRequest(query=response.original_query, request_id=response.request_id),
        QuerySignalExtractionService().extract(response.original_query),
    )
    assert session.rollbacks == 1
    assert response.persistence_status == "failed"
    assert response.qa_record_id is None
    assert "保存失败" in response.message


def test_unsupported_scope_returns_structured_abstention_without_retrieval_or_write() -> None:
    session = _FakeSession()
    repository = _FakeRepository()
    service = _service(session, repository)
    service.signals = QuerySignalExtractionService()
    service.scope = SimpleNamespace(
        scope_id="huawei_sun2000_competition_v1",
        partition_name="huawei_sun2000_competition_v1",
        allowed_document_ids=(),
    )
    payload = QueryAwareSearchRequest(
        query="阳光电源 SG110CX 告警如何处理",
        request_id="unsupported-request",
        persist_result=False,
    )
    response = service._unsupported_scope_response(
        payload,
        query=payload.query,
        reason="unsupported_manufacturer",
        total_started=0.0,
    )
    assert response.request_id == "unsupported-request"
    assert response.abstained is True
    assert response.references == []
    assert response.retrieved_chunks == []
    assert response.answer == QuerySignalExtractionService.FORMAL_SUPPORT_MESSAGE
    assert response.persistence_status == "skipped_preview"
    assert response.provider_status["keyword"] == "not_called"
    assert repository.created == []
