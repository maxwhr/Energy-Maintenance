from __future__ import annotations

import json
import re
from collections import Counter

from sqlalchemy import func, select

from task25b_r2_common import ROOT, masked_title, now_iso, sha256_text, write_csv, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument


TEST_TITLE = re.compile(r"^(task\s*\d+|task25|test|demo|fixture|synthetic|controlled)", re.I)
TEST_SOURCE_TYPES = {
    "test",
    "test_fixture",
    "synthetic",
    "controlled_benchmark",
    "task25b_controlled",
    "task25b_r1_controlled",
}


def _eligible_as_formal(document: KnowledgeDocument) -> tuple[bool, str]:
    metadata = document.metadata_json or {}
    source_type = (document.source_type or "").strip().lower()
    if TEST_TITLE.search((document.title or "").strip()):
        return False, "excluded_test_title"
    if source_type in TEST_SOURCE_TYPES or any(token in source_type for token in ("synthetic", "fixture", "controlled")):
        return False, "excluded_test_source_type"
    if any(bool(metadata.get(key)) for key in ("synthetic", "test_only", "controlled_benchmark", "task25b_seed")):
        return False, "excluded_test_metadata"
    if document.manufacturer not in {"huawei", "sungrow"}:
        return False, "unsupported_manufacturer"
    if document.device_type not in {"pv_inverter", "inverter"}:
        return False, "unsupported_device_type"
    return True, "approved_parsed_active_formal"


def _row(document: KnowledgeDocument, chunks: list[KnowledgeChunk]) -> dict:
    metadata = document.metadata_json or {}
    fault_codes = sorted(
        {
            str(code)
            for chunk in chunks
            for code in ((chunk.metadata_json or {}).get("fault_codes") or [])
            if code
        }
    )
    fault_categories = sorted(
        {
            str(value)
            for chunk in chunks
            for value in (
                (chunk.metadata_json or {}).get("fault_types")
                or [(chunk.metadata_json or {}).get("fault_type")]
            )
            if value
        }
    )
    formal, reason = _eligible_as_formal(document)
    digest_basis = "|".join(str(chunk.content_hash or "") for chunk in chunks)
    return {
        "document_id": str(document.id),
        "masked_title": masked_title(document.title),
        "document_type": document.document_type,
        "file_type": (document.file_ext or "unknown").lstrip(".").lower(),
        "device_types": [document.device_type],
        "manufacturers": [document.manufacturer],
        "fault_codes": fault_codes,
        "fault_categories": fault_categories,
        "chunk_count": len(chunks),
        "approved_at": document.reviewed_at,
        "document_version": metadata.get("document_version") or metadata.get("version") or "unspecified",
        "parser_version": metadata.get("parser_version") or document.parser_name or "unspecified",
        "chunker_version": metadata.get("chunker_version") or "unspecified",
        "content_hash": sha256_text(digest_basis),
        "selected": False,
        "selection_reason": reason,
        "privacy_risk": "metadata_only_report",
        "index_eligible": formal,
        "source_type": document.source_type,
    }


def _select(rows: list[dict]) -> list[dict]:
    eligible = [row for row in rows if row["index_eligible"] and row["chunk_count"] > 0]
    # Prefer business diversity, then enough chunks to reach the 300 target with at most 15 documents.
    eligible.sort(
        key=lambda row: (
            row["document_type"] not in {"manual", "alarm_code", "sop", "fault_case", "inspection_standard"},
            -min(row["chunk_count"], 100),
            row["document_id"],
        )
    )
    selected: list[dict] = []
    total = 0
    covered_types: set[str] = set()
    covered_makers: set[str] = set()
    while eligible and len(selected) < 15 and (len(selected) < 5 or total < 300):
        best = max(
            eligible,
            key=lambda row: (
                row["document_type"] not in covered_types,
                bool(set(row["manufacturers"]) - covered_makers),
                min(row["chunk_count"], max(0, 500 - total)),
            ),
        )
        if total and total + best["chunk_count"] > 800:
            fitting = [row for row in eligible if total + row["chunk_count"] <= 800]
            if not fitting:
                break
            best = max(fitting, key=lambda row: min(row["chunk_count"], max(0, 500 - total)))
        eligible.remove(best)
        best["selected"] = True
        best["selection_reason"] = "formal_diversity_and_chunk_target"
        selected.append(best)
        total += best["chunk_count"]
        covered_types.add(best["document_type"])
        covered_makers.update(best["manufacturers"])
    return selected


def _report(payload: dict) -> None:
    summary = payload["summary"]
    selected = payload["selected_documents"]
    lines = [
        "# Task 25B-R2 Pilot 正式文档选择报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 状态：{payload['status']}",
        f"- 候选文档：{summary['candidate_documents']}",
        f"- 严格正式候选：{summary['formal_candidate_documents']}",
        f"- 选中文档：{summary['selected_documents']}",
        f"- 选中 active Chunk：{summary['selected_active_chunks']}",
        f"- 300 Chunk 最低门槛：{'达到' if summary['minimum_achieved'] else '未达到'}",
        "- 正文输出：无；标题已掩码。",
        "- 正式文档修改：无。",
        "",
        "## 选中清单",
        "",
        "| document_id | masked_title | type | file | manufacturer | chunks | reason |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in selected:
        lines.append(
            f"| {row['document_id']} | {row['masked_title']} | {row['document_type']} | "
            f"{row['file_type']} | {','.join(row['manufacturers'])} | {row['chunk_count']} | "
            f"{row['selection_reason']} |"
        )
    path = ROOT / "docs" / "25B_R2_pilot_document_selection_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(KnowledgeDocument)
                .where(
                    KnowledgeDocument.review_status == "approved",
                    KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.status == "active",
                )
                .order_by(KnowledgeDocument.created_at, KnowledgeDocument.id)
            )
        )
        rows: list[dict] = []
        for document in documents:
            chunks = list(
                db.scalars(
                    select(KnowledgeChunk)
                    .where(
                        KnowledgeChunk.document_id == document.id,
                        KnowledgeChunk.status == "active",
                    )
                    .order_by(KnowledgeChunk.chunk_index)
                )
            )
            rows.append(_row(document, chunks))

    selected = _select(rows)
    selected_chunks = sum(row["chunk_count"] for row in selected)
    status = "READY" if 300 <= selected_chunks <= 800 else "BLOCKED_INSUFFICIENT_FORMAL_CORPUS"
    summary = {
        "candidate_documents": len(rows),
        "formal_candidate_documents": sum(bool(row["index_eligible"]) for row in rows),
        "selected_documents": len(selected),
        "selected_active_chunks": selected_chunks,
        "formal_chunks": selected_chunks,
        "synthetic_chunks": 0,
        "minimum_achieved": selected_chunks >= 300,
        "maximum_respected": selected_chunks <= 800,
        "file_types": dict(Counter(row["file_type"] for row in selected)),
        "document_types": dict(Counter(row["document_type"] for row in selected)),
        "manufacturers": dict(Counter(maker for row in selected for maker in row["manufacturers"])),
        "fault_code_count": len({code for row in selected for code in row["fault_codes"]}),
        "fault_categories": sorted({item for row in selected for item in row["fault_categories"]}),
    }
    payload = {
        "status": status,
        "generated_at": now_iso(),
        "selection_policy": {
            "required_document_status": ["approved", "parsed", "active"],
            "test_and_controlled_data_excluded": True,
            "target_documents": "5-15",
            "target_chunks": "300-500",
            "maximum_chunks": 800,
        },
        "summary": summary,
        "selected_documents": selected,
    }
    write_json("pilot_document_candidates.json", {"generated_at": now_iso(), "documents": rows})
    write_json("pilot_document_selection.json", payload)
    write_csv(
        "pilot_document_selection.csv",
        [
            "document_id", "masked_title", "document_type", "file_type", "device_types",
            "manufacturers", "fault_codes", "fault_categories", "chunk_count", "approved_at",
            "document_version", "parser_version", "chunker_version", "content_hash", "selected",
            "selection_reason", "privacy_risk", "index_eligible",
        ],
        rows,
    )
    _report(payload)
    print(json.dumps({"status": status, **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
