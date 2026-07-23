from uuid import uuid4

import pytest

from app.schemas.retrieval_scope import HUAWEI_SUN2000_COMPETITION_SCOPE_ID
from app.services.citation_validation_service import CitationValidationService
from app.services.retrieval_scope_service import RetrievalScopeService


def test_valid_citation_resolves_existing_document_and_chunk(
    db_session,
    approved_document,
) -> None:
    document, chunk = approved_document()
    result = CitationValidationService(db_session).validate(
        [{"document_id": str(document.id), "chunk_id": str(chunk.id)}],
        candidate_chunk_ids={chunk.id},
    )
    assert result.citation_valid is True
    assert result.valid_reference_ids == [str(chunk.id)]
    assert result.citation_coverage == 1.0


def test_invalid_chunk_identifier_is_rejected(db_session) -> None:
    result = CitationValidationService(db_session).validate(
        [{"chunk_id": "not-a-uuid"}],
        candidate_chunk_ids=set(),
    )
    assert result.citation_valid is False
    assert result.invalid_reference_reasons["not-a-uuid"] == "invalid_chunk_id"


def test_reference_must_be_in_final_candidate_set(
    db_session,
    approved_document,
) -> None:
    _, chunk = approved_document()
    result = CitationValidationService(db_session).validate(
        [{"chunk_id": str(chunk.id)}],
        candidate_chunk_ids={uuid4()},
    )
    assert result.citation_valid is False
    assert result.invalid_reference_reasons[str(chunk.id)] == "not_in_final_candidates"


@pytest.mark.parametrize(
    ("review_status", "chunk_status"),
    [("draft", "active"), ("approved", "inactive")],
)
def test_unapproved_or_inactive_source_is_rejected(
    db_session,
    approved_document,
    review_status: str,
    chunk_status: str,
) -> None:
    _, chunk = approved_document(
        review_status=review_status,
        chunk_status=chunk_status,
    )
    result = CitationValidationService(db_session).validate(
        [{"chunk_id": str(chunk.id)}],
        candidate_chunk_ids={chunk.id},
    )
    assert result.citation_valid is False
    assert result.grounded_warning


def test_citation_outside_requested_scope_is_rejected(
    db_session,
    approved_document,
) -> None:
    approved_document(manufacturer="huawei", product_series="SUN2000")
    _, sungrow_chunk = approved_document(manufacturer="sungrow", product_series="SG")
    huawei_scope = RetrievalScopeService(db_session).resolve(
        HUAWEI_SUN2000_COMPETITION_SCOPE_ID
    )
    result = CitationValidationService(db_session).validate(
        [{"chunk_id": str(sungrow_chunk.id)}],
        candidate_chunk_ids={sungrow_chunk.id},
        scope=huawei_scope,
    )
    assert result.citation_valid is False
    assert result.scope_mismatch_count == 1
