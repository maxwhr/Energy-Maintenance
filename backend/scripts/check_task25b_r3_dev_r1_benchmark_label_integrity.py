from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.services.query_understanding_service import QueryUnderstandingService
from task25b_r3_dev_common import ROOT, now_iso


DATASET = "task25b_r2_u3_r3_dev_zh_v1"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"
OUT.mkdir(parents=True, exist_ok=True)
ALLOWED = {
    "VALID", "STALE_CHUNK_ID", "SUPERSEDED_CHUNK", "WRONG_DOCUMENT", "WRONG_LANGUAGE",
    "NOT_PILOT_ELIGIBLE", "EMPTY_EXPECTED_LABEL", "NO_ANSWER_LABEL_ERROR", "MODEL_LABEL_ERROR",
    "ALARM_LABEL_ERROR", "AMBIGUOUS", "INVALID",
}


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET
        ).order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.created_at)))
        chunk_ids = {_uuid(value) for case in cases for value in (case.expected_chunk_ids or [])}; chunk_ids.discard(None)
        doc_ids = {_uuid(value) for case in cases for value in (case.expected_document_ids or [])}; doc_ids.discard(None)
        chunks = {item.id: item for item in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))}
        doc_ids.update(item.document_id for item in chunks.values())
        documents = {item.id: item for item in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids)))}
        eligible_docs = {item.id for item in db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.review_status == "approved", KnowledgeDocument.status == "active",
            KnowledgeDocument.metadata_json["normalized_language"].as_string() == "zh-CN",
            KnowledgeDocument.metadata_json["approved_for_pilot"].as_string() == "true",
            KnowledgeDocument.metadata_json["engineering_approved_for_pilot"].as_string() == "true",
        ))}
        eligible_chunks = set(db.scalars(select(KnowledgeChunk.id).join(KnowledgeDocument).where(
            KnowledgeChunk.status == "active", KnowledgeDocument.id.in_(eligible_docs)
        )))

        analysis_service = QueryUnderstandingService()
        details: list[dict] = []
        stale_items: list[dict] = []
        invalid_items: list[dict] = []
        corrections: list[dict] = []
        for case in cases:
            reasons: list[str] = []
            classification = "VALID"
            expected_chunks = [chunks.get(_uuid(value)) for value in (case.expected_chunk_ids or [])]
            expected_docs = [documents.get(_uuid(value)) for value in (case.expected_document_ids or [])]
            if case.category == "no_answer":
                if case.expected_chunk_ids or case.expected_document_ids or case.expected_media_ids:
                    classification, reasons = "NO_ANSWER_LABEL_ERROR", ["no-answer expected IDs must be empty"]
            elif not (case.expected_chunk_ids or case.expected_document_ids or case.expected_media_ids):
                classification, reasons = "EMPTY_EXPECTED_LABEL", ["answerable case has no expected evidence"]
            elif any(item is None for item in expected_chunks):
                classification, reasons = "STALE_CHUNK_ID", ["expected chunk does not exist"]
            elif any(item is None for item in expected_docs):
                classification, reasons = "INVALID", ["expected document does not exist"]
            elif any(item.status != "active" for item in expected_chunks if item):
                classification, reasons = "SUPERSEDED_CHUNK", ["expected chunk is not active"]
            elif any((documents.get(item.document_id).status != "active" or
                      (documents.get(item.document_id).metadata_json or {}).get("superseded_by_document_id"))
                     for item in expected_chunks if item and documents.get(item.document_id)):
                classification, reasons = "SUPERSEDED_CHUNK", ["expected document version is superseded"]
            elif any(item.document_id not in {_uuid(value) for value in (case.expected_document_ids or [])}
                     for item in expected_chunks if item):
                classification, reasons = "WRONG_DOCUMENT", ["expected chunk/document IDs are inconsistent"]
            else:
                all_docs = [documents[item.document_id] for item in expected_chunks if item]
                if any((item.metadata_json or {}).get("normalized_language") != "zh-CN" for item in all_docs):
                    classification, reasons = "WRONG_LANGUAGE", ["expected evidence is not normalized zh-CN"]
                elif any(item.id not in eligible_docs for item in all_docs) or any(item.id not in eligible_chunks for item in expected_chunks if item):
                    classification, reasons = "NOT_PILOT_ELIGIBLE", ["expected evidence is outside current engineering Pilot"]
                elif any(not (item.metadata_json or {}).get("source_locator") for item in expected_chunks if item):
                    classification, reasons = "AMBIGUOUS", ["expected chunk has no source locator"]

            analysis = analysis_service.understand(case.query_text)
            if classification == "VALID" and case.category == "device_model_query" and not analysis.device_models:
                classification, reasons = "MODEL_LABEL_ERROR", ["device-model category query contains no normalized device model"]
            if classification == "VALID" and case.category == "fault_code_query" and not analysis.fault_codes:
                classification, reasons = "ALARM_LABEL_ERROR", ["fault-code category query contains no alarm identifier"]
            if classification == "VALID" and case.category == "fault_code_query" and analysis.fault_codes:
                evidence = " ".join(item.content for item in expected_chunks if item)
                if not any(re.search(re.escape(code), evidence, re.I) for code in analysis.fault_codes):
                    classification, reasons = "ALARM_LABEL_ERROR", ["query alarm identifier is absent from expected chunk"]

            detail = {
                "case_id": str(case.id), "name": case.name, "category": case.category,
                "classification": classification, "reasons": reasons,
                "expected_document_ids": case.expected_document_ids or [], "expected_chunk_ids": case.expected_chunk_ids or [],
                "query_models": analysis.device_models, "query_alarm_identifiers": analysis.fault_codes,
                "source_locators": [(item.metadata_json or {}).get("source_locator") for item in expected_chunks if item],
            }
            if classification not in ALLOWED:
                raise RuntimeError(f"unsupported classification: {classification}")
            details.append(detail)
            if classification in {"STALE_CHUNK_ID", "SUPERSEDED_CHUNK"}:
                stale_items.append(detail)
            if classification not in {"VALID", "STALE_CHUNK_ID", "SUPERSEDED_CHUNK"}:
                invalid_items.append(detail)
            if classification in {"MODEL_LABEL_ERROR", "ALARM_LABEL_ERROR"}:
                corrections.append({
                    "case_id": str(case.id), "classification": classification, "old_query": case.query_text,
                    "old_expected_document_ids": json.dumps(case.expected_document_ids or []),
                    "old_expected_chunk_ids": json.dumps(case.expected_chunk_ids or []),
                    "proposed_action": "rebuild grounded query from expected document/chunk metadata and source locator in v2",
                    "new_expected_document_ids": json.dumps(case.expected_document_ids or []),
                    "new_expected_chunk_ids": json.dumps(case.expected_chunk_ids or []),
                    "source_locator": json.dumps(detail["source_locators"], ensure_ascii=False),
                })

    counts = Counter(item["classification"] for item in details)
    payload = {"generated_at": now_iso(), "dataset_version": DATASET, "total_cases": len(details),
               "classification_counts": dict(sorted(counts.items())), "details": details,
               "all_valid": counts.get("VALID", 0) == len(details), "expert_verified": False}
    _write(OUT / "benchmark_label_integrity.json", payload)
    _write(OUT / "stale_expected_ids.json", {"generated_at": now_iso(), "count": len(stale_items), "items": stale_items})
    _write(OUT / "invalid_expected_ids.json", {"generated_at": now_iso(), "count": len(invalid_items), "items": invalid_items})
    correction_path = OUT / "case_label_corrections.csv"
    with correction_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(corrections[0]) if corrections else ["case_id", "classification", "proposed_action"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(corrections)
    report = ROOT / "docs" / "25B_R3_DEV_R1_benchmark_label_integrity_report.md"
    report.write_text(
        "# Task 25B-R3-DEV-R1 Benchmark 标签完整性报告\n\n"
        f"- dataset：`{DATASET}`（只读失败基线）\n- cases：{len(details)}\n"
        f"- 分类：`{json.dumps(dict(sorted(counts.items())), ensure_ascii=False)}`\n"
        f"- stale/superseded：{len(stale_items)}\n- invalid/ambiguous/label errors：{len(invalid_items)}\n"
        f"- 建议修正并写入新版本的 cases：{len(corrections)}\n"
        "- 原 v1 标签和失败 run 未修改；任何修正只允许进入独立 v2。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASSED", "total": len(details), "counts": dict(counts),
                      "stale": len(stale_items), "invalid": len(invalid_items), "corrections": len(corrections)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
