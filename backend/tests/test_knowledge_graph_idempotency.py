from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import KGEvidenceLink, KGEdge, KGExtractionRun, KGNode
from app.services.kg_rule_extractor import KGExtractionSource, KGRuleExtractor
from app.services.knowledge_graph_service import (
    KnowledgeGraphPermissionError,
    KnowledgeGraphService,
)


def extraction_source(text: str) -> KGExtractionSource:
    source_id = uuid4()
    return KGExtractionSource(
        source_type="knowledge_document",
        source_id=source_id,
        text=text,
        manufacturer="huawei",
        product_series="SUN2000",
        document_id=source_id,
        chunk_id=uuid4(),
    )


def test_plain_numbers_do_not_create_alarm_nodes() -> None:
    candidates = KGRuleExtractor().extract(
        [extraction_source("SUN2000 released in 2026, rated at 1000 V and page 17.")]
    )
    alarms = [
        item
        for item in candidates
        if item["candidate_type"] == "node"
        and item["payload"]["node_type"] == "alarm"
    ]
    assert alarms == []


def test_fault_code_context_creates_alarm_node() -> None:
    candidates = KGRuleExtractor().extract(
        [extraction_source("SUN2000 Fault code 2031 indicates low insulation resistance.")]
    )
    alarm_names = {
        item["payload"]["canonical_name"]
        for item in candidates
        if item["candidate_type"] == "node"
        and item["payload"]["node_type"] == "alarm"
    }
    assert "2031" in alarm_names


def test_bootstrap_creates_business_nodes_and_edges(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document()
    result = KnowledgeGraphService(db_session).bootstrap(current_user=admin_user)
    assert result["processed_document_ids"]
    assert result["after"]["nodes"] > 0
    assert result["after"]["edges"] > 0


def test_repeated_bootstrap_is_idempotent(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved_document()
    service = KnowledgeGraphService(db_session)
    first = service.bootstrap(current_user=admin_user)
    second = service.bootstrap(current_user=admin_user)
    assert second["after"] == first["after"]
    assert second["processed_document_ids"] == []
    assert second["skipped_document_ids"]


def test_bootstrap_evidence_has_real_document_and_chunk(
    db_session,
    approved_document,
    admin_user,
) -> None:
    document, chunk = approved_document()
    KnowledgeGraphService(db_session).bootstrap(current_user=admin_user)
    evidence = list(db_session.scalars(select(KGEvidenceLink)))
    assert evidence
    assert all(item.document_id == document.id for item in evidence)
    assert all(item.chunk_id == chunk.id for item in evidence)
    assert all((item.evidence_text or "").strip() for item in evidence)


def test_bootstrap_ignores_unapproved_documents(
    db_session,
    approved_document,
    admin_user,
) -> None:
    approved, _ = approved_document()
    draft, _ = approved_document(
        title="Draft source",
        review_status="draft",
    )
    result = KnowledgeGraphService(db_session).bootstrap(current_user=admin_user)
    assert str(approved.id) in result["processed_document_ids"]
    assert str(draft.id) not in result["processed_document_ids"]
    assert db_session.scalar(select(func.count()).select_from(KGExtractionRun)) == 1


def test_engineer_cannot_initialize_graph(
    db_session,
    approved_document,
    make_user,
) -> None:
    approved_document()
    engineer = make_user(username="graph_engineer", role="engineer")
    with pytest.raises(KnowledgeGraphPermissionError):
        KnowledgeGraphService(db_session).bootstrap(current_user=engineer)
    assert db_session.scalar(select(func.count()).select_from(KGNode)) == 0
    assert db_session.scalar(select(func.count()).select_from(KGEdge)) == 0
