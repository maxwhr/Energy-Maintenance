import inspect

from app.services.citation_batch_builder_service import CitationBatchBuilderService


def test_citation_batch_builder_has_zero_sql_calls():
    source = inspect.getsource(CitationBatchBuilderService.validate_candidates)
    assert ".execute(" not in source
    assert ".get(" not in source or "locator.get" in source
