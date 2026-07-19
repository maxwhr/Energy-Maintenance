from app.services.vector_store_adapters import DashVectorAdapter


def test_pilot_query_filter_can_require_approved_parsed_active_rows():
    expression = DashVectorAdapter._filter_expression({
        "review_status": "approved", "parse_status": "parsed", "status": "active",
        "object_type": "formal_pilot_chunk",
    })
    assert "review_status = 'approved'" in expression
    assert "status = 'active'" in expression
    assert "archived" not in expression
