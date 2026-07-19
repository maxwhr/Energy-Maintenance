from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DATASET_PATH = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "task27a_huawei_sun2000_engineering_candidate_v1.json"
)
EVALUATION_PATH = PROJECT_ROOT / ".runtime" / "task27a" / "keyword_evaluation_exp5_normalized.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "project_audit" / "28_huawei_rag_expert_review_sheet.csv"
EXPECTED_DATASET_HASH = "9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0"


FIELDNAMES = [
    "case_id",
    "query",
    "expected_manufacturer",
    "expected_model",
    "expected_alarm_code",
    "expected_evidence_documents",
    "expected_chunks",
    "required_answer_points",
    "prohibited_claims",
    "safety_required",
    "should_abstain",
    "current_top_5",
    "current_answer",
    "current_references",
    "expert_conclusion",
    "labels_accurate",
    "answer_acceptable",
    "citation_supports",
    "safety_sufficient",
    "review_comments",
    "reviewer",
    "review_date",
    "expert_reviewed",
    "review_status",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_sheet(dataset_path: Path, evaluation_path: Path, output_path: Path) -> int:
    dataset_raw = dataset_path.read_bytes()
    dataset_hash = hashlib.sha256(dataset_raw).hexdigest()
    if dataset_hash != EXPECTED_DATASET_HASH:
        raise RuntimeError(f"DATASET_INTEGRITY_FAILURE: {dataset_hash}")

    dataset = json.loads(dataset_raw.decode("utf-8"))
    evaluation = _load_json(evaluation_path)
    if evaluation.get("evaluation_dataset", {}).get("sha256") != dataset_hash:
        raise RuntimeError("evaluation dataset hash does not match the frozen fixture")
    if evaluation.get("engineering_gate_metric_basis") != "strict":
        raise RuntimeError("expert material requires an evaluation whose gate basis is strict")

    cases_by_id = {item["case_id"]: item for item in evaluation.get("cases", [])}
    frozen_cases = dataset.get("cases", [])
    if len(frozen_cases) != 30 or len(cases_by_id) != 30:
        raise RuntimeError("expert material requires exactly 30 frozen and evaluated cases")

    rows: list[dict[str, Any]] = []
    for case in frozen_cases:
        evaluated = cases_by_id.get(case["case_id"])
        if evaluated is None:
            raise RuntimeError(f"missing evaluation case: {case['case_id']}")
        references = list(evaluated.get("actual", {}).get("references", []))[:5]
        top_five = [
            {
                "rank": index,
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "document_title": item.get("document_title") or item.get("title"),
                "score": item.get("score"),
            }
            for index, item in enumerate(references, start=1)
        ]
        document_titles = {
            str(item.get("document_id")): item.get("document_title") or item.get("title")
            for item in references
        }
        expected_documents = [
            {
                "document_id": document_id,
                "document_title": document_titles.get(str(document_id)),
            }
            for document_id in case["expected_document_ids"]
        ]
        rows.append({
            "case_id": case["case_id"],
            "query": case["query"],
            "expected_manufacturer": case["expected_manufacturer"],
            "expected_model": case["expected_model"],
            "expected_alarm_code": case["expected_alarm_code"],
            "expected_evidence_documents": _compact_json(expected_documents),
            "expected_chunks": _compact_json(case["expected_chunk_ids"]),
            "required_answer_points": _compact_json(case["required_answer_points"]),
            "prohibited_claims": _compact_json(case["prohibited_answer_points"]),
            "safety_required": str(bool(case["safety_required"])).lower(),
            "should_abstain": str(bool(case["should_abstain"])).lower(),
            "current_top_5": _compact_json(top_five),
            "current_answer": evaluated.get("actual", {}).get("answer", ""),
            "current_references": _compact_json(references),
            "expert_conclusion": "",
            "labels_accurate": "",
            "answer_acceptable": "",
            "citation_supports": "",
            "safety_sufficient": "",
            "review_comments": "",
            "reviewer": "",
            "review_date": "",
            "expert_reviewed": "false",
            "review_status": "pending",
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Task 27A Huawei expert review sheet")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--evaluation", type=Path, default=EVALUATION_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    count = build_sheet(args.dataset.resolve(), args.evaluation.resolve(), args.output.resolve())
    print(json.dumps({
        "status": "generated_pending_human_review",
        "row_count": count,
        "expert_reviewed": False,
        "review_status": "pending",
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
