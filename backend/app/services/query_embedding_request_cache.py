from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Callable


class QueryEmbeddingRequestCache:
    """Request-local cache with optional bounded short-TTL process reuse."""

    _shared: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()
    _lock = threading.Lock()

    def __init__(self, *, model: str, dimension: int, ttl_seconds: int = 600, max_entries: int = 512, shared_enabled: bool = False):
        self.model = model
        self.dimension = int(dimension)
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.shared_enabled = shared_enabled
        self._request: dict[str, list[float]] = {}
        self.hits = 0
        self.misses = 0

    def key(self, query: str) -> str:
        normalized_hash = hashlib.sha256(" ".join(query.split()).casefold().encode("utf-8")).hexdigest()
        return f"{self.model}:{self.dimension}:{normalized_hash}"

    def get_or_compute(self, query: str, callback: Callable[[], list[float]]) -> list[float]:
        key = self.key(query)
        if key in self._request:
            self.hits += 1
            return self._request[key]
        if self.shared_enabled:
            now = time.monotonic()
            with self._lock:
                cached = self._shared.get(key)
                if cached and cached[0] > now:
                    self.hits += 1
                    self._shared.move_to_end(key)
                    self._request[key] = cached[1]
                    return cached[1]
                if cached:
                    self._shared.pop(key, None)
        self.misses += 1
        vector = callback()
        if not vector:
            return vector
        self._request[key] = vector
        if self.shared_enabled:
            with self._lock:
                self._shared[key] = (time.monotonic() + self.ttl_seconds, vector)
                self._shared.move_to_end(key)
                while len(self._shared) > self.max_entries:
                    self._shared.popitem(last=False)
        return vector
