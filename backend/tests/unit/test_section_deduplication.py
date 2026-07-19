from types import SimpleNamespace

from app.services.result_set_refinement_service import ResultSetRefinementService


def test_same_content_is_collapsed_even_with_different_chunk_ids():
    items = [
        SimpleNamespace(chunk=SimpleNamespace(id="a", content="same", metadata_json={}, section_title="a", page_number=1), document=SimpleNamespace(id="d1", title="", product_series=None, model=None, metadata_json={}), score=.9),
        SimpleNamespace(chunk=SimpleNamespace(id="b", content="same", metadata_json={}, section_title="b", page_number=2), document=SimpleNamespace(id="d2", title="", product_series=None, model=None, metadata_json={}), score=.8),
    ]
    result = ResultSetRefinementService().refine(items, requested_top_k=5, analysis=None)
    assert len(result.surfaced) == 1
    assert result.diagnostics["duplicate_collapses"] == 1
