from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase
from app.services.grounded_benchmark_validation import topic_hint
from task25b_r3_dev_r4_common import DATASET_VERSION, OUT, now_iso, read_json, sha256_text, write_json


def ngrams(value: str) -> set[str]:
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())
    return {normalized[index:index + width] for width in (2, 3) for index in range(max(0, len(normalized) - width + 1))}


def overlap(left: str, right: str) -> float:
    a, b = ngrams(left), ngrams(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def main() -> None:
    semantic = read_json(OUT / "semantic_units.json")
    units = {unit["semantic_unit_id"]: unit for unit in (semantic.get("units") or [])}
    hint_counts = Counter(
        (unit.get("product_family"), topic_hint(unit).lower())
        for unit in units.values() if topic_hint(unit)
    )
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET_VERSION,
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
        ).order_by(RetrievalEvaluationCase.name)))
        query_counts = Counter(case.query_text for case in cases)
        rows = []
        hard_failures = 0
        for case in cases:
            metadata = dict(case.metadata_json or {})
            no_answer = bool(metadata.get("is_no_answer"))
            expected_unit_ids = metadata.get("expected_semantic_unit_ids") or []
            unit = units.get(expected_unit_ids[0]) if len(expected_unit_ids) == 1 else None
            reasons = []
            if no_answer:
                if case.expected_chunk_ids or case.expected_document_ids or expected_unit_ids:
                    reasons.append("no_answer_expected_ids_not_empty")
                status = "GROUNDED_STRONG" if not reasons else "INVALID"
                lexical_leakage = False
                lexical_value = 0.0
            else:
                if unit is None: reasons.append("expected_semantic_unit_missing_or_not_unique")
                if unit and metadata.get("source_hash") != unit.get("source_hash"): reasons.append("source_hash_mismatch")
                if unit and set(case.expected_chunk_ids or []) != set(unit.get("source_chunk_ids") or []): reasons.append("source_chunk_mapping_mismatch")
                if unit and not all(str(concept).lower() in unit["canonical_text"].lower() for concept in (metadata.get("grounding_concepts") or [])):
                    reasons.append("query_concept_not_supported_by_source_unit")
                if query_counts[case.query_text] != 1: reasons.append("ambiguous_duplicate_query")
                source_excerpt = unit["canonical_text"].split("原文证据：", 1)[-1] if unit else ""
                lexical_value = overlap(case.query_text, source_excerpt) if unit else 1.0
                lexical_leakage = False
                if metadata.get("is_vector_heavy"):
                    hint = str(metadata.get("ambiguity_free_topic_hint") or "").strip()
                    if not hint: reasons.append("ambiguity_free_topic_hint_missing")
                    if hint and unit and hint.lower() not in unit["canonical_text"].lower():
                        reasons.append("topic_hint_not_source_supported")
                    if hint and unit and hint_counts[(unit.get("product_family"), hint.lower())] != 1:
                        reasons.append("topic_hint_not_unique_within_product")
                    if hint and hint.lower() not in case.query_text.lower():
                        reasons.append("topic_hint_not_present_in_query")
                    if int(metadata.get("ambiguity_free_revision") or 0) < 2:
                        reasons.append("ambiguity_free_revision_missing")
                    if lexical_value >= 0.18: reasons.append("lexical_overlap_too_high")
                    if unit and any(model and model.lower() in case.query_text.lower() for model in unit.get("device_models") or []):
                        reasons.append("complete_model_leakage")
                    if unit and any(code and code.lower() in case.query_text.lower() for code in unit.get("alarm_codes") or []):
                        reasons.append("complete_alarm_code_leakage")
                    if unit and unit.get("source_section") and unit["source_section"].lower() in case.query_text.lower():
                        reasons.append("complete_section_title_leakage")
                    if unit and unit["semantic_unit_id"] in case.query_text: reasons.append("source_id_leakage")
                    if unit and case.query_text.strip() == unit.get("canonical_text", "").strip():
                        reasons.append("exact_anchor_leakage")
                    lexical_leakage = any("leakage" in reason or "overlap" in reason for reason in reasons)
                status = "GROUNDED_STRONG" if not reasons else ("AMBIGUOUS" if "ambiguous_duplicate_query" in reasons else "GROUNDING_WEAK")
            engineering_grounded = status == "GROUNDED_STRONG"
            if not engineering_grounded:
                hard_failures += 1
            metadata.update({
                "grounding_status": status, "grounding_reason": reasons or ["source_and_lexical_checks_passed"],
                "engineering_grounded": engineering_grounded, "lexical_leakage": lexical_leakage,
                "lexical_overlap": round(lexical_value, 6), "human_expert_verified": False, "expert_verified": False,
                "engineering_check_version": "task25b_r3_dev_r4_dual_check_v1",
            })
            case.metadata_json = metadata
            rows.append({
                "case_id": str(case.id), "case_name": case.name, "split": case.dataset_split, "category": case.category,
                "query_hash": sha256_text(case.query_text), "vector_heavy": bool(metadata.get("is_vector_heavy")),
                "semantic_unit_id_hash": sha256_text(expected_unit_ids[0]) if expected_unit_ids else None,
                "grounding_status": status, "lexical_overlap": round(lexical_value, 6),
                "lexical_leakage": lexical_leakage, "engineering_grounded": engineering_grounded,
                "human_expert_verified": False, "reasons": reasons or ["source_and_lexical_checks_passed"],
            })
        db.commit()
    summary = Counter(row["grounding_status"] for row in rows)
    result = {
        "generated_at": now_iso(), "dataset": DATASET_VERSION, "total_cases": len(rows), "summary": dict(sorted(summary.items())),
        "vector_heavy": sum(row["vector_heavy"] for row in rows), "lexical_leakage": sum(row["lexical_leakage"] for row in rows),
        "engineering_verified": sum(row["engineering_grounded"] for row in rows), "expert_verified": 0,
        "weak": summary.get("GROUNDING_WEAK", 0), "ambiguous": summary.get("AMBIGUOUS", 0),
        "test_data_used": False, "passed": hard_failures == 0 and len(rows) >= 80,
        "rows": rows,
    }
    write_json("grounding_audit.json", result)
    with (OUT / "grounding_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow({key: __import__("json").dumps(value, ensure_ascii=False) if isinstance(value, list) else value for key, value in row.items()})
    print({"status": "PASSED" if result["passed"] else "FAILED", "total": len(rows), "summary": result["summary"], "vector_heavy": result["vector_heavy"], "lexical_leakage": result["lexical_leakage"]})
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
