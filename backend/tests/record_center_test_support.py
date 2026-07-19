from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.record_center_query_repository import RECORD_TYPE_ORDER


def item_ids(items: list[dict[str, Any]]) -> list[str]:
    return [f"{item['record_type']}:{item['record_id']}" for item in items]


def sort_key(item: dict[str, Any]) -> tuple:
    value = item.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (value, -RECORD_TYPE_ORDER.index(item["record_type"]), str(item["record_id"]))

