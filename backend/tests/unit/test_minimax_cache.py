import time

from app.services.minimax_resilience import TTLCache


def test_ttl_cache_is_lru_bounded_and_returns_copies() -> None:
    cache = TTLCache[dict](max_entries=2, ttl_seconds=0.02)
    cache.set("a", {"value": [1]})
    cache.set("b", {"value": [2]})
    assert cache.get("a") == {"value": [1]}
    cache.set("c", {"value": [3]})
    assert cache.get("b") is None
    item = cache.get("a")
    item["value"].append(9)
    assert cache.get("a") == {"value": [1]}
    time.sleep(0.03)
    assert cache.get("a") is None
