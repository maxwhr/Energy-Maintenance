from __future__ import annotations

import hashlib
import json
from threading import RLock
from typing import Any


class RecordCenterCacheInvalidationService:
    """Version source for a future bounded cache; Task 25E keeps response caching disabled."""

    _lock = RLock()
    _data_version = 0

    @classmethod
    def current_version(cls) -> int:
        with cls._lock:
            return cls._data_version

    @classmethod
    def invalidate(cls, _reason: str = "record_center_write") -> int:
        with cls._lock:
            cls._data_version += 1
            return cls._data_version

    @classmethod
    def cache_key(
        cls,
        *,
        user_id: str,
        role: str,
        permission_fingerprint: str,
        filters: dict[str, Any],
        page: int,
        page_size: int,
        sort_direction: str,
    ) -> str:
        payload = {
            "user_id": user_id,
            "role": role,
            "permission_fingerprint": permission_fingerprint,
            "filters": filters,
            "page": page,
            "page_size": page_size,
            "sort_direction": sort_direction,
            "data_version": cls.current_version(),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return "record-center:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

