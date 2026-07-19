from types import SimpleNamespace

from app.services.result_set_refinement_service import ResultSetRefinementService


def _item(value: str, score: float):
    return SimpleNamespace(chunk=SimpleNamespace(id=value, content=value, metadata_json={}, section_title=value, page_number=1),
                           document=SimpleNamespace(id=value, title=value, product_series=None, model=None, metadata_json={}), score=score)


def test_dynamic_top_k_stops_at_large_score_drop_without_hiding_top_result():
    result = ResultSetRefinementService(margin_threshold=.2).refine([_item("a", .9), _item("b", .5)], requested_top_k=5, analysis=None)
    assert len(result.surfaced) == 1
    assert result.diagnostics["cutoff_reason"] == "LARGE_SCORE_DROP"
