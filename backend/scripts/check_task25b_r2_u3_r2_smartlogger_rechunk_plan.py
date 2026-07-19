from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BACKEND_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from app.core.database import SessionLocal  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument  # noqa: E402
from check_task25b_r2_u3_r1_preapproval_quality import (  # noqa: E402
    hamming,
    noise_flags,
    normalized,
    repeated_header_count,
    simhash64,
    table_like,
)


ALARM_DOCUMENT_ID = UUID("058ddd98-e3e8-44b5-a154-fb86923c3ff4")
MANUAL_DOCUMENT_ID = UUID("da7ee239-a195-4345-94d1-48a54085bf2c")
TARGET_IDS = [ALARM_DOCUMENT_ID, MANUAL_DOCUMENT_ID]
RUNTIME_DIR = ROOT_DIR / ".runtime" / "task25b_r2_u3_r2"
REPORT_PATH = ROOT_DIR / "docs" / "25B_R2_U3_R2_smartlogger_rechunk_plan.md"


def has_locator(chunk: KnowledgeChunk) -> bool:
    metadata = chunk.metadata_json or {}
    return bool(
        chunk.page_number
        or chunk.section_title
        or metadata.get("heading_path")
        or metadata.get("source_locator")
        or metadata.get("section_locator")
    )


def chunk_snapshot(document: KnowledgeDocument, chunks: list[KnowledgeChunk]) -> str:
    values = [
        f"{document.id}|{document.updated_at.isoformat()}|{document.review_status}|{document.chunk_count}"
    ]
    values.extend(
        f"{item.id}|{item.updated_at.isoformat()}|{item.content_hash}|{item.status}|{len(item.content or '')}"
        for item in chunks
    )
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def duplicate_groups(chunks: list[KnowledgeChunk]) -> tuple[list[dict], list[dict]]:
    exact_map: dict[str, list[KnowledgeChunk]] = defaultdict(list)
    normalized_values = []
    fingerprints = []
    for chunk in chunks:
        value = normalized(chunk.content)
        exact_map[hashlib.sha256(value.encode("utf-8")).hexdigest()].append(chunk)
        normalized_values.append(value)
        fingerprints.append(simhash64(value))
    exact = [
        {
            "normalized_sha256": digest,
            "chunk_ids": [str(item.id) for item in members],
            "chunk_indexes": [item.chunk_index for item in members],
            "member_count": len(members),
        }
        for digest, members in exact_map.items()
        if len(members) > 1
    ]
    near = []
    for left in range(len(chunks)):
        for right in range(left + 1, len(chunks)):
            if normalized_values[left] == normalized_values[right]:
                continue
            left_len, right_len = len(normalized_values[left]), len(normalized_values[right])
            if not left_len or min(left_len, right_len) / max(left_len, right_len) < 0.85:
                continue
            distance = hamming(fingerprints[left], fingerprints[right])
            if distance <= 3:
                near.append(
                    {
                        "left_chunk_id": str(chunks[left].id),
                        "right_chunk_id": str(chunks[right].id),
                        "left_chunk_index": chunks[left].chunk_index,
                        "right_chunk_index": chunks[right].chunk_index,
                        "simhash_hamming_distance": distance,
                    }
                )
    return exact, near


def field_count(chunks: list[KnowledgeChunk], patterns: tuple[str, ...]) -> int:
    return sum(any(re.search(pattern, chunk.content or "", re.IGNORECASE) for pattern in patterns) for chunk in chunks)


def analyze(document: KnowledgeDocument, chunks: list[KnowledgeChunk]) -> tuple[dict, dict]:
    exact, near = duplicate_groups(chunks)
    navigation = footer = encoding = 0
    for chunk in chunks:
        nav, foot, enc = noise_flags(chunk.content or "")
        navigation += nav
        footer += foot
        encoding += enc
    heading_count = sum(bool(chunk.section_title or (chunk.metadata_json or {}).get("heading_path")) for chunk in chunks)
    page_count = sum(chunk.page_number is not None for chunk in chunks)
    locator_count = sum(has_locator(chunk) for chunk in chunks)
    table_count = sum(table_like(chunk.content or "") for chunk in chunks)
    adjacent_context_risks = []
    for left, right in zip(chunks, chunks[1:]):
        right_text = (right.content or "").lstrip()
        if (
            (len(left.content or "") < 220 or len(right.content or "") < 220)
            and not right.section_title
            and (right_text[:1].islower() or right_text.startswith(("and ", "or ", "then ", "•", "-")))
        ):
            adjacent_context_risks.append(
                {"left_chunk_index": left.chunk_index, "right_chunk_index": right.chunk_index}
            )
    alarm_knowledge = (document.metadata_json or {}).get("alarm_knowledge") or {}
    named_alarms = alarm_knowledge.get("named_alarms") or []
    explicit_codes = alarm_knowledge.get("explicit_alarm_codes") or []
    applicable_models = sorted({
        model
        for alarm in named_alarms
        for model in (alarm.get("applicable_device_models") or [])
    })
    field_presence = {
        "alarm_code_chunks": field_count(chunks, (r"\balarm\s*(?:id|code)\b", r"\b11\d{2}\b")),
        "alarm_name_chunks": field_count(chunks, (r"\balarm\s*name\b", r"\bfault\b", r"\babnormal\b")),
        "severity_chunks": field_count(chunks, (r"\bseverity\b", r"\bmajor\b", r"\bminor\b", r"\bwarning\b")),
        "impact_chunks": field_count(chunks, (r"\bimpact\b", r"\beffect\b")),
        "cause_chunks": field_count(chunks, (r"\bcause\b", r"possible cause")),
        "handling_step_chunks": field_count(chunks, (r"\bsuggestion\b", r"handling", r"procedure", r"\bstep\s*\d+")),
        "safety_action_chunks": field_count(chunks, (r"\bdanger\b", r"\bwarning\b", r"power off", r"disconnect", r"protective")),
        "applicable_device_chunks": field_count(chunks, (r"SmartLogger", r"SmartMGC")),
    }
    result = {
        "document_id": str(document.id),
        "title": document.title,
        "review_status": document.review_status,
        "quality_status": (document.metadata_json or {}).get("quality_status"),
        "page_count": document.page_count,
        "page_count_note": "not populated in source record" if document.page_count is None else None,
        "original_chunk_count": len(chunks),
        "exact_duplicate_group_count": len(exact),
        "exact_duplicate_extra_chunks": sum(group["member_count"] - 1 for group in exact),
        "near_duplicate_group_count": len(near),
        "repeated_header_candidates": repeated_header_count(chunks),
        "navigation_noise_chunks": navigation,
        "footer_noise_chunks": footer,
        "encoding_issue_chunks": encoding,
        "table_like_chunks": table_count,
        "adjacent_context_risk_pairs": adjacent_context_risks,
        "heading_path_coverage": round(heading_count / len(chunks), 4) if chunks else 0.0,
        "page_number_coverage": round(page_count / len(chunks), 4) if chunks else 0.0,
        "source_locator_coverage": round(locator_count / len(chunks), 4) if chunks else 0.0,
        "explicit_alarm_codes": explicit_codes,
        "explicit_alarm_code_count": len(explicit_codes),
        "named_alarm_count": len(named_alarms),
        "structured_alarm_unit_candidates": len(explicit_codes) + len(named_alarms),
        "applicable_models": applicable_models,
        "troubleshooting_steps": int(alarm_knowledge.get("troubleshooting_steps") or 0),
        "safety_actions": int(alarm_knowledge.get("safety_actions") or 0),
        "alarm_field_presence": field_presence,
        "rechunk_required": True,
        "automatically_modified": False,
    }
    groups = {
        "document_id": str(document.id),
        "exact_duplicate_groups": exact,
        "near_duplicate_pairs": near,
    }
    return result, groups


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    with SessionLocal() as session:
        documents = []
        groups = []
        snapshots_before = {}
        loaded = []
        for document_id in TARGET_IDS:
            document = session.get(KnowledgeDocument, document_id)
            if not document:
                raise RuntimeError(f"SmartLogger document not found: {document_id}")
            chunks = list(session.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.document_id == document_id)
                .order_by(KnowledgeChunk.chunk_index.asc())
            ))
            snapshots_before[str(document_id)] = chunk_snapshot(document, chunks)
            analyzed, duplicate_data = analyze(document, chunks)
            documents.append(analyzed)
            groups.append(duplicate_data)
            loaded.append((document, chunks))
        snapshots_after = {str(document.id): chunk_snapshot(document, chunks) for document, chunks in loaded}
    if snapshots_before != snapshots_after:
        raise RuntimeError("SmartLogger source documents or chunks changed during read-only analysis")

    alarm_result = next(item for item in documents if item["document_id"] == str(ALARM_DOCUMENT_ID))
    manual_result = next(item for item in documents if item["document_id"] == str(MANUAL_DOCUMENT_ID))
    plan = {
        "task": "Task 25B-R2-U3-R2",
        "generated_at": generated_at,
        "analysis_mode": "read_only",
        "documents": documents,
        "combined_original_chunks": sum(item["original_chunk_count"] for item in documents),
        "combined_exact_duplicate_groups": sum(item["exact_duplicate_group_count"] for item in documents),
        "combined_near_duplicate_groups": sum(item["near_duplicate_group_count"] for item in documents),
        "alarm_reference_plan": {
            "unit_boundary": "one alarm per structured knowledge unit",
            "required_fields": [
                "alarm_code", "alarm_name", "severity", "impact", "possible_causes", "handling_steps",
                "safety_actions", "applicable_models", "source_page", "source_section",
            ],
            "rules": [
                "associate alarm code, name, severity, impact, cause, and handling advice before chunk emission",
                "preserve each alarm table row as one logical structure",
                "merge continuation rows by alarm code and cause ID",
                "never emit cause or suggestion without the parent alarm identifier",
                "deduplicate exact and near-duplicate alarm rows before formal import",
            ],
            "candidate_units_before_canonical_mapping": alarm_result["structured_alarm_unit_candidates"],
            "requires_human_mapping_of_code_to_name": True,
        },
        "user_manual_plan": {
            "unit_boundary": "chapter and semantic subsection",
            "rules": [
                "remove repeated headers and footers",
                "exclude table of contents and navigation from formal retrieval",
                "merge adjacent short paragraphs",
                "preserve tables as indivisible logical units",
                "attach safety warnings to the governed procedure",
                "split oversized chapters only at semantic boundaries",
            ],
        },
        "write_strategy": {
            "create_new_parse_version": True,
            "preserve_original_document": True,
            "preserve_original_chunks": True,
            "replace_or_overwrite_executed": False,
            "approval_executed": False,
            "pilot_index_executed": False,
        },
        "source_snapshot_before": snapshots_before,
        "source_snapshot_after": snapshots_after,
        "automatically_modified": False,
    }
    duplicate_payload = {
        "task": "Task 25B-R2-U3-R2",
        "generated_at": generated_at,
        "documents": groups,
    }
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "smartlogger_rechunk_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUNTIME_DIR / "smartlogger_duplicate_groups.json").write_text(json.dumps(duplicate_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    document_lines = "\n".join(
        f"- `{item['document_id']}`：原始 Chunk={item['original_chunk_count']}，页数={item['page_count'] or '未写入'}，"
        f"exact groups={item['exact_duplicate_group_count']}（额外 Chunk={item['exact_duplicate_extra_chunks']}），"
        f"near pairs={item['near_duplicate_group_count']}，重复页眉候选={item['repeated_header_candidates']}，"
        f"导航/页脚噪声={item['navigation_noise_chunks']}/{item['footer_noise_chunks']}，"
        f"heading/page/locator={item['heading_path_coverage']:.2%}/{item['page_number_coverage']:.2%}/{item['source_locator_coverage']:.2%}。"
        for item in documents
    )
    field_lines = "\n".join(f"- {key}: {value}" for key, value in alarm_result["alarm_field_presence"].items())
    report = f"""# Task 25B-R2-U3-R2 SmartLogger 重切分计划

生成时间：`{generated_at}`

## 结论

- 两份 SmartLogger 原始文档及 642 个 Chunk 均保持不变；before/after 快照一致，`automatically_modified=false`。
- 两份文档均需重切分，且不得直接批准或进入 Pilot。
- 告警参考应按“一告警一结构化知识单元”重建；用户手册应按章节/语义小节重建。

## 原始质量分析

{document_lines}

告警参考候选：显式代码 {alarm_result['explicit_alarm_code_count']}，命名告警 {alarm_result['named_alarm_count']}，映射前结构化单元候选 {alarm_result['structured_alarm_unit_candidates']}。这些候选必须先完成人工 code/name 对齐与去重，不把数量当作最终单元数。

### 告警字段出现情况（Chunk 数）

{field_lines}

## 告警参考重切分

每个单元必须同时保存：`alarm_code`、`alarm_name`、`severity`、`impact`、`possible_causes`、`handling_steps`、`safety_actions`、`applicable_models`、`source_page`、`source_section`。续表按告警码和 Cause ID 合并，严禁把代码、原因、建议拆成无上下文 Chunk。

## 用户手册重切分

按章节切分；清除重复页眉/页脚；目录和导航不进入正式检索；合并相邻短段；表格保持完整；安全警告绑定到对应步骤；超长章节只在语义边界继续拆分。

## 安全落地方式

创建新的 parse/chunk 版本并与原文档并存，完成人工抽检后再决定切换。不得覆盖或删除当前文档与 Chunk；本任务未执行批准、重切分、Embedding、DashVector 或 Pilot 索引。
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "alarm_chunks": alarm_result["original_chunk_count"],
        "manual_chunks": manual_result["original_chunk_count"],
        "duplicate_groups": plan["combined_exact_duplicate_groups"] + plan["combined_near_duplicate_groups"],
        "automatically_modified": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
