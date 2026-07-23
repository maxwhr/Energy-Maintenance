from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import func, select

from app.models import QARecord
from app.main import create_api_router
from app.api.routes.system import get_system_status
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import (
    HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
    SUNGROW_SG_FORMAL_SCOPE_ID,
)
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.retrieval_service import RetrievalService


def request(question: str, **overrides) -> RetrievalQueryRequest:
    values = {
        "question": question,
        "persist_result": False,
        "enable_llm": False,
        "allow_real_api": False,
        "enable_vector": False,
        "retrieval_mode": "keyword",
        "top_k": 5,
        "min_score": 0.0,
    }
    values.update(overrides)
    return RetrievalQueryRequest(**values)


def registered_api_paths(*, retrieval_lab_enabled: bool) -> set[str]:
    app = FastAPI()
    app.include_router(
        create_api_router(retrieval_lab_enabled=retrieval_lab_enabled)
    )
    return set(app.openapi()["paths"])


def test_detects_huawei_scope_from_question() -> None:
    resolved = RetrievalService._resolve_retrieval_scope(
        request("Huawei SUN2000 low insulation resistance")
    )
    assert resolved.manufacturer == "huawei"
    assert resolved.product_series == "SUN2000"
    assert resolved.scope_id == HUAWEI_SUN2000_COMPETITION_SCOPE_ID


def test_detects_sungrow_scope_from_question() -> None:
    resolved = RetrievalService._resolve_retrieval_scope(
        request("Sungrow SG series inverter alarm handling")
    )
    assert resolved.manufacturer == "sungrow"
    assert resolved.product_series == "SG"
    assert resolved.scope_id == SUNGROW_SG_FORMAL_SCOPE_ID


def test_explicit_huawei_scope_takes_precedence() -> None:
    resolved = RetrievalService._resolve_retrieval_scope(
        request(
            "generic inverter fault",
            manufacturer="huawei",
            product_series="SUN2000",
        )
    )
    assert (resolved.manufacturer, resolved.product_series) == ("huawei", "SUN2000")


def test_explicit_sungrow_scope_takes_precedence() -> None:
    resolved = RetrievalService._resolve_retrieval_scope(
        request(
            "generic inverter fault",
            manufacturer="sungrow",
            product_series="SG",
        )
    )
    assert (resolved.manufacturer, resolved.product_series) == ("sungrow", "SG")


def test_unknown_scope_uses_safe_default() -> None:
    resolved = RetrievalService._resolve_retrieval_scope(
        request("generic inverter maintenance question")
    )
    assert (resolved.manufacturer, resolved.product_series) == ("huawei", "SUN2000")


def test_huawei_scope_excludes_sungrow_documents(db_session, approved_document) -> None:
    huawei_document, _ = approved_document(manufacturer="huawei", product_series="SUN2000")
    approved_document(manufacturer="sungrow", product_series="SG")
    scope = RetrievalScopeService(db_session).resolve(HUAWEI_SUN2000_COMPETITION_SCOPE_ID)
    assert scope is not None
    assert scope.allowed_document_ids == (huawei_document.id,)


def test_sungrow_scope_excludes_huawei_documents(db_session, approved_document) -> None:
    approved_document(manufacturer="huawei", product_series="SUN2000")
    sungrow_document, _ = approved_document(manufacturer="sungrow", product_series="SG")
    scope = RetrievalScopeService(db_session).resolve(SUNGROW_SG_FORMAL_SCOPE_ID)
    assert scope is not None
    assert scope.allowed_document_ids == (sungrow_document.id,)


def test_huawei_query_returns_only_huawei_citations(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document(
        manufacturer="huawei",
        product_series="SUN2000",
        content=(
            "Huawei SUN2000 low insulation resistance fault. "
            "Check DC cable insulation and grounding before restart."
        ),
    )
    approved_document(
        manufacturer="sungrow",
        product_series="SG",
        content="Sungrow SG inverter low insulation resistance reference.",
    )
    response = RetrievalService(db_session, allow_real_api=False).query(
        request("Huawei SUN2000 low insulation resistance"),
        admin_user,
    )
    assert response.references
    assert {item.manufacturer for item in response.references} == {"huawei"}


def test_sungrow_query_returns_only_sungrow_citations(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document(
        manufacturer="huawei",
        product_series="SUN2000",
        content="Huawei SUN2000 communication alarm reference.",
    )
    approved_document(
        manufacturer="sungrow",
        product_series="SG",
        content=(
            "Sungrow SG series inverter alarm handling. "
            "Check communication wiring and grounding."
        ),
    )
    response = RetrievalService(db_session, allow_real_api=False).query(
        request("Sungrow SG series inverter alarm handling"),
        admin_user,
    )
    assert response.references
    assert {item.manufacturer for item in response.references} == {"sungrow"}


def test_no_evidence_returns_controlled_refusal_without_qa_write(
    db_session,
    admin_user,
) -> None:
    before = db_session.scalar(select(func.count()).select_from(QARecord))
    response = RetrievalService(db_session, allow_real_api=False).query(
        request(
            "Sungrow SG unsupported insulation failure",
            manufacturer="sungrow",
            product_series="SG",
        ),
        admin_user,
    )
    after = db_session.scalar(select(func.count()).select_from(QARecord))
    assert response.insufficient_evidence is True
    assert response.references == []
    assert response.retrieved_chunks == []
    assert before == after == 0


def test_retrieval_lab_routes_are_not_registered_when_disabled() -> None:
    paths = registered_api_paths(retrieval_lab_enabled=False)
    assert "/api/retrieval/scope/r1-status" not in paths
    assert "/api/system/retrieval-quality/r5/summary" not in paths


def test_retrieval_lab_routes_are_registered_when_enabled() -> None:
    paths = registered_api_paths(retrieval_lab_enabled=True)
    assert "/api/retrieval/scope/r1-status" in paths
    assert "/api/retrieval/scope/r4-status" in paths
    assert "/api/system/retrieval-quality/r5/summary" in paths


def test_production_status_uses_database_evidence_without_runtime_artifacts(
    db_session,
    approved_document,
    monkeypatch,
) -> None:
    huawei_document, huawei_chunk = approved_document(
        manufacturer="huawei",
        product_series="SUN2000",
    )
    sungrow_document, _ = approved_document(
        manufacturer="sungrow",
        product_series="SG",
    )
    db_session.add(
        QARecord(
            question="SUN2000 low insulation resistance",
            normalized_query="sun2000 low insulation resistance",
            manufacturer="huawei",
            product_series="SUN2000",
            device_type="pv_inverter",
            answer="Check DC insulation.",
            references=[
                {
                    "document_id": str(huawei_document.id),
                    "chunk_id": str(huawei_chunk.id),
                }
            ],
            retrieved_chunks=[],
            suggested_steps=[],
            safety_notes=[],
            related_history=[],
            confidence=0.8,
            trace_id="production-status-citation",
        )
    )
    db_session.flush()

    def reject_artifact_read(*_args, **_kwargs):
        raise AssertionError("production status must not read runtime artifacts")

    monkeypatch.setattr(Path, "read_text", reject_artifact_read)
    response = get_system_status(db_session)
    retrieval = response["data"]["retrieval"]

    assert response["data"]["database_status"] == "online"
    assert retrieval["approved_active_document_count"] == 2
    assert retrieval["approved_active_chunk_count"] == 2
    assert retrieval["manufacturers"] == ["huawei", "sungrow"]
    assert retrieval["citation_count"] == 1
    assert retrieval["valid_citation_count"] == 1
    assert retrieval["citation_validity_rate"] == 1.0
    assert retrieval["lab_enabled"] is False
    assert "pilot_routing" not in response["data"]
    assert sungrow_document.id is not None
