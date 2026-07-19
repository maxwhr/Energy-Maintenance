from types import SimpleNamespace

from app.services.result_set_refinement_service import ResultSetRefinementService


def test_pipeline_returns_one_to_five_surfaced_results():
    items = [SimpleNamespace(chunk=SimpleNamespace(id=str(index), content=str(index), metadata_json={}, section_title=str(index), page_number=1), document=SimpleNamespace(id=str(index), title="", product_series=None, model=None, metadata_json={}), score=.9 - index * .02) for index in range(8)]
    assert 1 <= len(ResultSetRefinementService().refine(items, requested_top_k=10, analysis=None).surfaced) <= 5
