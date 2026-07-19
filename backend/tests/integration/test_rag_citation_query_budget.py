import inspect

from app.services.citation_batch_builder_service import CitationBatchBuilderService
from app.services.citation_validation_service import validate_source_locator


def test_citation_batch_builder_has_zero_sql_calls():
    source = inspect.getsource(CitationBatchBuilderService.validate_candidates)
    locator_source = inspect.getsource(validate_source_locator)
    assert ".execute(" not in source
    assert "locator.get" in locator_source
