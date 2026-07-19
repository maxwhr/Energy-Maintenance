from types import SimpleNamespace
from uuid import uuid4

from app.services.citation_batch_builder_service import CitationBatchBuilderService


def test_loaded_pdf_candidate_builds_valid_citation_without_repository_call():
    document_id = uuid4()
    chunk = SimpleNamespace(status="active", metadata_json={}, page_number=8, section_title="处理步骤")
    document = SimpleNamespace(
        id=document_id, review_status="approved", status="active", parse_status="parsed",
        metadata_json={"normalized_language": "zh-CN", "approved_for_pilot": True, "engineering_approved_for_pilot": True},
        source_type="vendor_official_pdf", source="manual.pdf",
    )
    candidate = SimpleNamespace(
        chunk=chunk, document=document, chunk_id="chunk-a", scope_validation_passed=True,
        source_locator={"page_start": 8, "section": "处理步骤"},
    )
    scope = SimpleNamespace(
        allowed_document_ids=(document_id,), required_document_status="approved", required_chunk_status="active",
        normalized_language="zh-CN", approved_for_pilot=True, include_alternate_language=False,
        include_test_fixture=False, include_marketing=False,
    )
    result = CitationBatchBuilderService().validate_candidates([candidate], scope=scope)
    assert result.valid_reference_ids == ["chunk-a"]
    assert result.citation_coverage_ratio == 1.0


def test_pdf_page_and_document_title_are_a_valid_traceable_fallback_without_section():
    document_id = uuid4()
    chunk = SimpleNamespace(status="active", metadata_json={}, page_number=8, section_title=None, content="connector procedure")
    document = SimpleNamespace(
        id=document_id, title="SUN2000 quick guide", review_status="approved", status="active", parse_status="parsed",
        metadata_json={"normalized_language": "zh-CN", "approved_for_pilot": True, "engineering_approved_for_pilot": True},
        source_type="vendor_official_pdf", source="manual.pdf",
    )
    candidate = SimpleNamespace(
        chunk=chunk, document=document, chunk_id="chunk-title-page", scope_validation_passed=True,
        source_locator={"page_number": 8, "section_path": []},
    )
    scope = SimpleNamespace(
        allowed_document_ids=(document_id,), required_document_status="approved", required_chunk_status="active",
        normalized_language="zh-CN", approved_for_pilot=True, include_alternate_language=False,
        include_test_fixture=False, include_marketing=False,
    )
    result = CitationBatchBuilderService().validate_candidates([candidate], scope=scope)
    assert result.valid_reference_ids == ["chunk-title-page"]


def test_pdf_title_fallback_requires_page_and_nonempty_chunk_content():
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id, title="SUN2000 quick guide", review_status="approved", status="active", parse_status="parsed",
        metadata_json={"normalized_language": "zh-CN", "approved_for_pilot": True, "engineering_approved_for_pilot": True},
        source_type="vendor_official_pdf", source="manual.pdf",
    )
    scope = SimpleNamespace(
        allowed_document_ids=(document_id,), required_document_status="approved", required_chunk_status="active",
        normalized_language="zh-CN", approved_for_pilot=True, include_alternate_language=False,
        include_test_fixture=False, include_marketing=False,
    )
    missing_page = SimpleNamespace(
        chunk=SimpleNamespace(status="active", metadata_json={}, page_number=None, section_title=None, content="evidence"),
        document=document, chunk_id="missing-page", scope_validation_passed=True, source_locator={"section_path": []},
    )
    empty_content = SimpleNamespace(
        chunk=SimpleNamespace(status="active", metadata_json={}, page_number=8, section_title=None, content=""),
        document=document, chunk_id="empty-content", scope_validation_passed=True, source_locator={"page_number": 8},
    )
    result = CitationBatchBuilderService().validate_candidates([missing_page, empty_content], scope=scope)
    assert result.valid_reference_ids == []
    assert result.invalid_reference_reasons == {
        "missing-page": "missing_pdf_page_or_section_locator",
        "empty-content": "empty_chunk_content",
    }
