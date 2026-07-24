from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy import func, select

from app.models import QARecord
from app.schemas.retrieval import RetrievalQueryRequest, RetrievalQueryResponse
from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalDecision
from app.services.citation_validation_service import CitationValidationResult
from app.services.retrieval_service import RetrievalService
from app.services.vector_index_service import VerifiedVectorHit


def request(question: str, **overrides) -> RetrievalQueryRequest:
    values = {
        "question": question,
        "persist_result": False,
        "enable_llm": False,
        "allow_real_api": False,
        "enable_vector": False,
        "enable_kg_enhancement": False,
        "retrieval_mode": "keyword",
        "top_k": 5,
        "min_score": 0.0,
    }
    values.update(overrides)
    return RetrievalQueryRequest(**values)


class _FixedFuture:
    def __init__(self, value):
        self.value = value

    def result(self, timeout=None):
        return self.value


class _FixedExecutor:
    def __init__(self, value):
        self.value = value

    def submit(self, *_args, **_kwargs):
        return _FixedFuture(self.value)


class _TimeoutFuture:
    def result(self, timeout=None):
        raise FutureTimeoutError


class _TimeoutExecutor:
    def submit(self, *_args, **_kwargs):
        return _TimeoutFuture()


def test_vector_timeout_falls_back_to_keyword(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document(
        content=(
            "Huawei SUN2000 low insulation resistance fault. "
            "Check DC cable insulation and grounding before restart."
        )
    )
    service = RetrievalService(db_session, allow_real_api=False)
    service.candidate_coordinator.executor = _TimeoutExecutor()

    response = service.query(
        request(
            "Huawei SUN2000 low insulation resistance",
            retrieval_mode="hybrid",
            enable_vector=True,
        ),
        admin_user,
    )

    assert response.references
    assert response.actual_strategy == "keyword"
    assert response.vector_fallback_used is True
    assert response.fallback_reason == "vector_time_budget_exceeded"
    assert response.retrieval_diagnostics["vector_timeout"] is True


def test_strong_keyword_evidence_is_protected(
    db_session,
    approved_document,
    admin_user,
    monkeypatch,
) -> None:
    document, chunk = approved_document(
        content=(
            "Huawei SUN2000 low insulation resistance fault. "
            "Check DC cable insulation and grounding before restart."
        )
    )
    vector_hit = VerifiedVectorHit(
        chunk=chunk,
        document=document,
        score=0.9,
        vector_id=str(chunk.id),
        metadata={},
        raw_score=0.9,
    )
    service = RetrievalService(db_session, allow_real_api=False)
    service.candidate_coordinator.executor = _FixedExecutor(
        (
            [vector_hit],
            {
                "vector_backend": "test",
                "vector_available": True,
                "fallback_reason": None,
                "external_call_counts": {
                    "embedding": 0,
                    "dashvector": 0,
                    "cloud_llm": 0,
                    "mimo": 0,
                    "ocr": 0,
                },
            },
        )
    )
    monkeypatch.setattr(
        service.strategy_router,
        "route",
        lambda *_args, **_kwargs: AdaptiveRetrievalDecision(
            requested_strategy="adaptive",
            recommended_strategy="hybrid",
            actual_strategy="hybrid",
            fallback_strategy="keyword",
            routing_reason="test_semantic_route",
            keyword_weight=0.3,
            vector_weight=0.7,
            reranker_requested=False,
        ),
    )

    response = service.query(
        request(
            "Huawei SUN2000 low insulation resistance",
            retrieval_mode="adaptive",
            enable_vector=True,
        ),
        admin_user,
    )

    assert response.references
    assert response.actual_strategy == "keyword"
    assert response.fallback_reason == "strong_keyword_evidence_protected"
    assert response.retrieval_diagnostics["quality_fallback_used"] is True


def test_citation_validation_warning_is_preserved(
    db_session,
    approved_document,
    admin_user,
    monkeypatch,
) -> None:
    approved_document()
    service = RetrievalService(db_session, allow_real_api=False)
    warning = "Citation validation warning"
    monkeypatch.setattr(
        service.citation_service,
        "validate",
        lambda *_args, **_kwargs: CitationValidationResult(
            citation_valid=False,
            citation_coverage=0.0,
            invalid_reference_ids=["invalid"],
            grounded_warning=warning,
        ),
    )

    response = service.query(
        request("Huawei SUN2000 low insulation resistance"),
        admin_user,
    )

    assert warning in response.answer
    assert response.retrieval_diagnostics["citation_valid"] is False
    assert response.retrieval_diagnostics["grounded_warning"] == warning


def test_persist_false_with_evidence_writes_no_qa(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document()
    before = db_session.scalar(select(func.count()).select_from(QARecord))

    RetrievalService(db_session, allow_real_api=False).query(
        request("Huawei SUN2000 low insulation resistance", persist_result=False),
        admin_user,
    )

    after = db_session.scalar(select(func.count()).select_from(QARecord))
    assert before == after == 0


def test_persist_true_creates_exactly_one_qa(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document()
    before = db_session.scalar(select(func.count()).select_from(QARecord))

    RetrievalService(db_session, allow_real_api=False).query(
        request("Huawei SUN2000 low insulation resistance", persist_result=True),
        admin_user,
    )

    after = db_session.scalar(select(func.count()).select_from(QARecord))
    assert before == 0
    assert after == 1


def test_vector_worker_uses_an_isolated_session(
    db_session,
    monkeypatch,
) -> None:
    captured = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def expunge(self, _item):
            raise AssertionError("No vector hits should be detached in this test")

    class FakeVectorIndexService:
        def __init__(self, db, **_kwargs):
            captured["db"] = db

        def search(self, *_args, **_kwargs):
            return [], {"vector_available": False}

    isolated_session = FakeSession()
    service = RetrievalService(db_session, allow_real_api=False)
    service.candidate_coordinator.session_factory = lambda: isolated_session
    monkeypatch.setattr(
        "app.services.retrieval_candidate_coordinator.VectorIndexService",
        FakeVectorIndexService,
    )

    service.candidate_coordinator._vector_search_isolated(
        "query",
        5,
        {},
    )

    assert captured["db"] is isolated_session
    assert captured["db"] is not db_session


def test_response_contract_and_external_call_counts_are_unchanged(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document()
    response = RetrievalService(db_session, allow_real_api=False).query(
        request("Huawei SUN2000 low insulation resistance"),
        admin_user,
    )

    assert set(response.model_dump()) == set(RetrievalQueryResponse.model_fields)
    assert response.external_call_counts == {
        "embedding": 0,
        "dashvector": 0,
        "cloud_llm": 0,
        "mimo": 0,
        "ocr": 0,
    }
    assert response.retrieval_diagnostics["external_call_counts"] == (
        response.external_call_counts
    )


def test_knowledge_graph_enhancement_off_and_on(
    db_session,
    approved_document,
    admin_user,
    monkeypatch,
) -> None:
    approved_document()
    service = RetrievalService(db_session, allow_real_api=False)
    monkeypatch.setattr(
        "app.services.retrieval_response_builder.KnowledgeGraphService.business_context",
        lambda *_args, **_kwargs: {
            "kg_nodes": [{"id": "node-1"}],
            "kg_edges": [{"id": "edge-1"}],
            "evidence": [{"document_id": "document-1"}],
            "graph_paths": [{"node_ids": ["node-1"]}],
        },
    )

    disabled = service.query(
        request(
            "Huawei SUN2000 low insulation resistance",
            enable_kg_enhancement=False,
        ),
        admin_user,
    )
    enabled = service.query(
        request(
            "Huawei SUN2000 low insulation resistance",
            enable_kg_enhancement=True,
        ),
        admin_user,
    )

    assert disabled.kg_context == {}
    assert disabled.kg_nodes == []
    assert enabled.kg_nodes == [{"id": "node-1"}]
    assert enabled.kg_edges == [{"id": "edge-1"}]
    assert enabled.kg_evidence == [{"document_id": "document-1"}]
    assert enabled.kg_paths == [{"node_ids": ["node-1"]}]
