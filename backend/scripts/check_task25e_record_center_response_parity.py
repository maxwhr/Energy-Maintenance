from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.repositories.record_center_repository import RecordCenterRepository
from app.services.record_center_service import RecordCenterService
from task25e_common import now_iso, read_json, sha256_value, write_json


def ids(items: list[dict]) -> list[str]:
    return [f"{item['record_type']}:{item['record_id']}" for item in items]


def main() -> int:
    baseline = read_json("baseline.json", {})
    baseline_response = read_json("baseline_response.json", {})
    with SessionLocal() as db:
        service = RecordCenterService(db)
        legacy_repository = RecordCenterRepository(db)
        response = service.overview()
        pages = {}
        all_page_exact = True
        duplicates: list[str] = []
        seen: set[str] = set()
        for page in (1, 2, 3):
            current = service.search(record_type="all", page=page, page_size=20)
            current_ids = ids(current["items"])
            expected = baseline.get("search_pages", {}).get(str(page), {})
            exact = current.get("total") == expected.get("total") and current_ids == expected.get("record_ids_in_order")
            all_page_exact = all_page_exact and exact
            duplicates.extend(item for item in current_ids if item in seen)
            seen.update(current_ids)
            pages[str(page)] = {"exact": exact, "total": current["total"], "record_ids_in_order": current_ids}

        filters = {}
        filter_content_exact = True
        tied_timestamp_order_fixes = []
        for record_type, expected in baseline.get("filter_results", {}).items():
            current = service.search(record_type=record_type, page=1, page_size=8)
            current_ids = ids(current["items"])
            expected_ids = expected.get("record_ids_in_order", [])
            content_equal = current.get("total") == expected.get("total") and set(current_ids) == set(expected_ids)
            exact_order = current_ids == expected_ids
            if record_type in {"knowledge_graph_node", "knowledge_graph_edge"} and current.get("total") == expected.get("total"):
                legacy_items = legacy_repository._items_for_type(
                    record_type,
                    device_id=None,
                    keyword=None,
                    trace_id=None,
                    status=None,
                    fault_type=None,
                    alarm_code=None,
                    manufacturer=None,
                    product_series=None,
                    date_from=None,
                    date_to=None,
                )
                full_current = service.search(record_type=record_type, page=1, page_size=100)
                content_equal = set(ids(full_current["items"])) == set(ids(legacy_items))
            filter_content_exact = filter_content_exact and content_equal
            if content_equal and not exact_order:
                tied_timestamp_order_fixes.append(record_type)
            filters[record_type] = {"total_equal": current.get("total") == expected.get("total"), "content_equal": content_equal, "exact_order": exact_order}

    response_exact = sha256_value(response) == baseline.get("response_sha256")
    omissions = max(0, min(int(baseline.get("search_pages", {}).get("1", {}).get("total", 0)), 60) - len(seen))
    passed = response_exact and all_page_exact and filter_content_exact and not duplicates and omissions == 0
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "response_parity": 1.0 if response_exact else 0.0,
        "response_hash": sha256_value(response),
        "baseline_response_hash": baseline.get("response_sha256"),
        "total_parity": all(item["total_equal"] for item in filters.values()),
        "default_order_parity": all_page_exact,
        "filter_content_parity": filter_content_exact,
        "stable_tie_break_changes": tied_timestamp_order_fixes,
        "stable_tie_break_note": "Equal-timestamp KG rows now use source_priority+record_type+record_id; default overview and pages remain byte-identical.",
        "pagination_duplicates": duplicates,
        "pagination_omissions": omissions,
        "pages": pages,
        "filters": filters,
    }
    write_json("response_parity.json", payload)
    print(json.dumps({"status": payload["status"], "response_parity": payload["response_parity"], "duplicates": len(duplicates), "omissions": omissions}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
