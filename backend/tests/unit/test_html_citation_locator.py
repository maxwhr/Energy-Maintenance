import inspect

from app.services.citation_validation_service import validate_source_locator


def test_html_citation_accepts_url_and_section_locator():
    source = inspect.getsource(validate_source_locator)
    assert "html_anchor" in source and "source_url" in source
    assert "missing_html_url_or_section_locator" in source
