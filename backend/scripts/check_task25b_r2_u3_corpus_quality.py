from __future__ import annotations

import json
from collections import Counter

from task25b_r2_u3_common import RUNTIME, is_official_url, now_iso, write_csv, write_json


def main() -> int:
    internal = json.loads((RUNTIME / "huawei_support_html_internal.json").read_text(encoding="utf-8"))
    records = []
    for item in internal.get("records", []):
        content = item.get("content") or ""
        reasons = []
        if not item.get("official_source") or not is_official_url(item.get("source_url") or ""):
            reasons.append("official_source")
        if not item.get("content_hash") or not item.get("question_title"):
            reasons.append("required_metadata")
        if not item.get("product_family") and not item.get("equipment_categories"):
            reasons.append("equipment_metadata")
        if len(content) < 80:
            reasons.append("minimum_content_length")
        gibberish = content.count("�") / max(1, len(content))
        if gibberish > 0.02:
            reasons.append("gibberish")
        status = "READY_FOR_HUMAN_REVIEW" if not reasons else "NEEDS_METADATA"
        records.append({
            **{key: value for key, value in item.items() if key != "content"},
            "quality_status": status, "quality_reasons": reasons,
            "content_length": len(content), "gibberish_ratio": round(gibberish, 6),
            "source_locator_available": bool(item.get("section_locator")),
            "marketing_only": False, "duplicate": False,
        })
    counts = Counter(item["quality_status"] for item in records)
    payload = {
        "generated_at": now_iso(), "checked": len(records), "quality_status_counts": dict(counts),
        "ready_for_human_review": counts.get("READY_FOR_HUMAN_REVIEW", 0),
        "needs_metadata": counts.get("NEEDS_METADATA", 0), "marketing_only": 0,
        "duplicate": 0, "invalid": 0, "automatic_approval": False, "records": records,
    }
    write_json("u3_corpus_quality.json", payload)
    write_csv("u3_corpus_quality.csv", [
        "source_url", "page_title", "question_title", "product_family", "equipment_categories",
        "document_type", "content_hash", "content_length", "quality_status", "quality_reasons",
        "source_locator_available", "marketing_only", "duplicate",
    ], records)
    print(json.dumps({k: payload[k] for k in ("checked", "ready_for_human_review", "needs_metadata", "marketing_only", "duplicate", "invalid")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
