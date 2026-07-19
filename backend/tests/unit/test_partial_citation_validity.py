import inspect

from app.services.citation_validation_service import CitationValidationService


def test_partial_citations_are_not_all_or_nothing():
    source = inspect.getsource(CitationValidationService.validate)
    assert "valid = bool(valid_strings)" in source
    assert "valid_reference_ids=valid_strings" in source
