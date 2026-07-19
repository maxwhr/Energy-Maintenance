import inspect

from app.services.vector_index_service import VectorIndexService


def test_vector_store_receives_no_none_filter():
    source = inspect.getsource(VectorIndexService.search)
    assert "if value is not None" in source
    assert 'or "pv_inverter"' not in source
