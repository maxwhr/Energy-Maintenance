from types import SimpleNamespace

from app.services.result_set_refinement_service import ResultSetRefinementService


def _item(chunk_id: str, document_id: str, section: str, score: float):
    return SimpleNamespace(chunk=SimpleNamespace(id=chunk_id, content=f"content-{chunk_id}", metadata_json={}, section_title=section, page_number=1),
                           document=SimpleNamespace(id=document_id, title="doc", product_series="SUN2000", model=None, metadata_json={}), score=score)


def test_refinement_collapses_same_section_and_limits_document_results():
    result = ResultSetRefinementService().refine([_item("1", "d1", "s1", .9), _item("2", "d1", "s1", .8), _item("3", "d1", "s2", .82)], requested_top_k=5, analysis=None)
    assert [item.chunk.id for item in result.surfaced] == ["1", "3"]
    assert result.diagnostics["section_collapses"] == 1
