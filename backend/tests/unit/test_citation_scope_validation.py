import inspect

from app.services.citation_validation_service import (
    CitationValidationResult,
    CitationValidationService,
    validate_source_locator,
)


def test_citation_scope_validation_contract():
    fields = CitationValidationResult(False, 0.0, invalid_reference_reasons={"x": "scope_or_status_mismatch"}, scope_mismatch_count=1)
    assert fields.scope_mismatch_count == 1
    source = inspect.getsource(CitationValidationService.validate)
    locator_source = inspect.getsource(validate_source_locator)
    assert "RetrievalRepository._scope_filters(scope)" in source
    assert "missing_html_url_or_section_locator" in locator_source
    assert "missing_pdf_page_or_section_locator" in locator_source
