from pathlib import Path


def test_frontend_search_has_debounce_abort_and_inflight_dedup():
    root = Path(__file__).resolve().parents[3]
    source = (root / "frontend" / "src" / "views" / "knowledge" / "Search.vue").read_text(encoding="utf-8")
    assert "setTimeout" in source
    assert "AbortController" in source
    assert "activeRequestKey === requestKey" in source
    assert "onUnmounted" in source
