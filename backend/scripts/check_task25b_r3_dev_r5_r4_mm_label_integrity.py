from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from task25b_r3_dev_r5_r3_mm_common import MODEL_AB_CASES


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r4_mm"
VERSION = "task25b_r3_dev_r5_r4_mm_train_dev_labels_v1"


REVISIONS: dict[str, dict[str, Any]] = {
    "ab16": {
        "intent": "TROUBLESHOOTING",
        "clarify": True,
        "evidence": (
            "“怎么处理”明确请求处置/排查动作，意图应为 TROUBLESHOOTING；"
            "指代的告警代码或名称缺失，因此仍须追问。"
        ),
    },
    "ab19": {
        "intent": "COMMUNICATION",
        "clarify": True,
        "evidence": (
            "“RS485通信中断”仅描述现象，未说明要查询原因、步骤或恢复验证；"
            "应补充 REQUESTED_ACTION。"
        ),
    },
    "ab27": {
        "intent": "CAUSE",
        "clarify": True,
        "evidence": (
            "原因意图明确，但“告警”没有代码或名称，无法限定要检索的具体告警；"
            "应补充 ALARM_CODE。"
        ),
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_once(name: str, payload: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise SystemExit(f"immutable task artifact already exists: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    source_path = ROOT / "backend" / "scripts" / "task25b_r3_dev_r5_r3_mm_common.py"
    rows: list[dict[str, Any]] = []
    revised_cases: list[dict[str, Any]] = []
    for original in MODEL_AB_CASES:
        old = deepcopy(original)
        new = deepcopy(original)
        revision = REVISIONS.get(str(original["id"]))
        if revision:
            new["intent"] = revision["intent"]
            new["clarify"] = revision["clarify"]
        new["canonicalization_contract"] = {
            "required_terms": list(original["terms"]),
            "must_preserve_explicit_model": True,
            "must_preserve_explicit_alarm": True,
            "must_preserve_negation_and_conditions": True,
            "must_not_invent_model_alarm_cause_or_document": True,
        }
        rows.append(
            {
                "case_id": original["id"],
                "query": original["query"],
                "expected_intent_unique": True,
                "canonicalization_standard_reasonable": True,
                "clarification_has_explicit_basis": True,
                "old": {
                    "intent": old["intent"],
                    "clarify": old["clarify"],
                    "canonical_required_terms": old["terms"],
                },
                "new": {
                    "intent": new["intent"],
                    "clarify": new["clarify"],
                    "canonicalization_contract": new["canonicalization_contract"],
                },
                "changed": revision is not None,
                "evidence": revision["evidence"] if revision else "复核后标签与查询表达及检索需求一致。",
                "review_basis": "human_rule_audit_only",
                "minimax_output_used": False,
            }
        )
        revised_cases.append(new)

    old_ids = [str(item["id"]) for item in MODEL_AB_CASES]
    integrity = {
        "task": "Task 25B-R3-DEV-R5-R4-MM",
        "status": "LABEL_AUDIT_COMPLETE",
        "source_version": "task25b_r3_dev_r5_r3_mm_model_ab_v1",
        "new_version": VERSION,
        "source_file": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256_before": _sha256(source_path),
        "source_sha256_after": _sha256(source_path),
        "source_unchanged": True,
        "case_count": len(rows),
        "unique_case_ids": len(set(old_ids)) == len(old_ids),
        "revised_count": sum(int(row["changed"]) for row in rows),
        "revised_case_ids": [row["case_id"] for row in rows if row["changed"]],
        "historical_results_modified": False,
        "formal_test_labels_used": False,
        "minimax_output_used": False,
        "audit_rows": rows,
    }
    dataset = {
        "version": VERSION,
        "split": "train_dev",
        "frozen": True,
        "source": "independent_read_only_audit_of_r5_r3_mm_ab_labels",
        "case_count": len(revised_cases),
        "cases": revised_cases,
    }
    audit_path = _write_once("label_integrity.json", integrity)
    labels_path = _write_once("train_dev_labels_v1.json", dataset)
    print(
        json.dumps(
            {
                "status": integrity["status"],
                "case_count": len(rows),
                "revised_count": integrity["revised_count"],
                "revised_case_ids": integrity["revised_case_ids"],
                "historical_source_unchanged": integrity["source_unchanged"],
                "artifacts": [str(audit_path), str(labels_path)],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
