from __future__ import annotations

import json

from task25g_r1_common import now_iso, read_json, write_json


def main() -> int:
    baseline = read_json("leakage_baseline.json", {})
    forensics = read_json("archived_evidence_forensics.json", [])
    categories = {
        "pending_leakage": "pending",
        "archived_leakage": "archived",
        "superseded_leakage": "superseded",
        "marketing_leakage": "marketing",
        "english_leakage": "english",
        "approval_leakage": "approval_invalid",
    }
    actual_counts = {
        output_name: sum(bool(item.get("actual_state_flags", {}).get(flag)) for item in forensics)
        for output_name, flag in categories.items()
    }
    original = baseline.get("original_reported_counts") or {}
    false_positive_labels = []
    for output_name in ("pending_leakage", "marketing_leakage"):
        original_count = int(original.get(output_name) or 0)
        actual_count = int(actual_counts[output_name])
        if original_count > actual_count:
            false_positive_labels.append(
                {
                    "classification": output_name,
                    "original_count": original_count,
                    "actual_count": actual_count,
                    "false_positive_count": original_count - actual_count,
                }
            )
    payload = {
        "version": "task25g_r1_scope_classification_v1",
        "generated_at": now_iso(),
        "status": "PASS" if len(forensics) == 12 else "FAIL",
        "evidence_count": len(forensics),
        "actual_counts": actual_counts,
        "classification_false_positive_evidence_count": len(
            {
                item["evidence_id"]
                for item in forensics
                if item.get("actual_state_flags", {}).get("archived")
                and not item.get("actual_state_flags", {}).get("pending")
                and not item.get("actual_state_flags", {}).get("marketing")
            }
        ),
        "classification_false_positive_assignments": sum(
            item["false_positive_count"] for item in false_positive_labels
        ),
        "false_positive_labels": false_positive_labels,
        "document_state_dimensions_independent": True,
        "actual_state_fields": [
            "document_lifecycle_status",
            "document_review_status",
            "document_category",
            "document_language",
            "document_parse_status",
            "source_type",
        ],
    }
    write_json("scope_classification.json", payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "actual_counts": actual_counts,
                "false_positive_evidence": payload["classification_false_positive_evidence_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
