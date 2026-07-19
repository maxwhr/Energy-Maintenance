from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, MaintenanceSemanticAnchor
from task25b_r3_dev_r5_r5_common import (
    ANCHOR_MATRIX_VERSION,
    DATASET_VERSION,
    OUT,
    RERANK_VERSION,
    SOURCE,
    now_iso,
    sha256_file,
    sha256_json,
    write_once,
)


SOURCE_DATASET = SOURCE / "train_dev_dataset_v1.json"
TARGET_CASES = 80


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def expected_requested_information(query: str, old_intent: str) -> list[str]:
    patterns = {
        "CAUSE": ("为什么", "为何", "啥原因", "什么原因", "原因", "怎么回事", "导致"),
        "ACTION": ("怎么办", "处理", "排查", "检查什么", "先查", "怎么查", "解决", "怎么修"),
        "PROCEDURE": ("步骤", "流程", "顺序操作", "按什么顺序", "如何更换", "如何操作", "如何恢复", "如何回收"),
        "SAFETY": ("安全", "风险", "危险", "带电", "触电", "防护", "注意"),
        "ALARM_MEANING": ("告警含义", "什么意思", "故障码", "告警代码", "告警码"),
        "PREREQUISITE": ("操作前", "开始前", "前提", "前置", "准备", "先满足", "哪些条件"),
        "VERIFICATION": ("验证", "确认", "是否恢复", "是否正常", "完成后", "处理完以后", "巡检结束"),
        "CONFIGURATION": ("配置", "设置", "参数", "地址", "波特率"),
    }
    output = [name for name, terms in patterns.items() if any(term in query for term in terms)]
    fallback = {
        "CAUSE": "CAUSE",
        "TROUBLESHOOTING": "ACTION",
        "PROCEDURE": "PROCEDURE",
        "SAFETY": "SAFETY",
        "ALARM": "ALARM_MEANING",
        "PREREQUISITE": "PREREQUISITE",
        "VERIFICATION": "VERIFICATION",
    }.get(old_intent)
    if fallback and fallback not in output:
        output.append(fallback)
    if not output:
        output.append("GENERAL_INFORMATION")
    return unique(output)[:5]


def expected_primary_intent(query: str, requested: list[str], old_intent: str) -> str:
    requested_set = set(requested)
    if "PROCEDURE" in requested_set or {"PREREQUISITE", "VERIFICATION"}.issubset(requested_set):
        return "PROCEDURE"
    if "ACTION" in requested_set and ("CAUSE" in requested_set or old_intent in {"COMMUNICATION", "TROUBLESHOOTING"}):
        return "TROUBLESHOOTING"
    if "SAFETY" in requested_set and len(requested_set) == 1:
        return "SAFETY"
    if "VERIFICATION" in requested_set and len(requested_set) == 1:
        return "VERIFICATION"
    if "PREREQUISITE" in requested_set and len(requested_set) == 1:
        return "PREREQUISITE"
    if "CAUSE" in requested_set:
        return "CAUSE"
    if "ALARM_MEANING" in requested_set:
        return "ALARM"
    if old_intent == "COMMUNICATION":
        return "COMMUNICATION"
    return old_intent if old_intent in {
        "TROUBLESHOOTING", "CAUSE", "PROCEDURE", "SAFETY", "ALARM",
        "COMMUNICATION", "PREREQUISITE", "VERIFICATION", "GENERAL",
    } else "GENERAL"


def section_id(document_id: str, locator: dict[str, Any]) -> str:
    value = json.dumps(locator, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"section:{document_id}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def semantic_mapping() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    with SessionLocal() as db:
        anchors = db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
            MaintenanceSemanticAnchor.index_status == "indexed",
            MaintenanceSemanticAnchor.current_version.is_(True),
        )).all()
        for anchor in anchors:
            fields = dict(anchor.semantic_fields or {})
            unit_id = str(fields.get("semantic_unit_id") or "")
            if not unit_id:
                continue
            item = mapping.setdefault(unit_id, {
                "semantic_unit_id": unit_id,
                "source_chunk_ids": [],
                "document_id": str(anchor.document_id),
                "source_locator": dict(anchor.source_locator or {}),
                "unit_types": [],
                "representation_versions": [],
            })
            item["source_chunk_ids"] = unique([
                *item["source_chunk_ids"],
                *(fields.get("source_chunk_ids") or [str(anchor.source_chunk_id)]),
            ])
            item["unit_types"] = unique([*item["unit_types"], str(anchor.anchor_type)])
            item["representation_versions"] = unique([
                *item["representation_versions"], anchor.semantic_representation_version,
            ])
    return mapping


def chunk_locator_mapping() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    with SessionLocal() as db:
        chunks = db.scalars(select(KnowledgeChunk)).all()
        for chunk in chunks:
            metadata = dict(chunk.metadata_json or {})
            locator = dict(metadata.get("source_locator") or {})
            if not locator and (chunk.section_title or chunk.page_number is not None):
                locator = {
                    "section": chunk.section_title,
                    "heading_path": [chunk.section_title] if chunk.section_title else [],
                    "page_start": chunk.page_number,
                    "page_end": chunk.page_number,
                    "source_chunk_ids": [str(chunk.id)],
                }
            mapping[str(chunk.id)] = locator
    return mapping


def union_row(first: dict[str, Any], second: dict[str, Any], *, ordinal: int) -> dict[str, Any]:
    row = deepcopy(first)
    row["query"] = f"{first['query'].rstrip('？?')}；同时还想知道：{second['query']}"
    for key in ("expected_document_ids", "expected_chunk_ids", "expected_semantic_unit_ids"):
        row[key] = unique([*(first.get(key) or []), *(second.get(key) or [])])
    row["source_locators"] = [
        value for value in [first.get("source_locator"), second.get("source_locator")] if value
    ]
    row["source_excerpts"] = unique([first.get("source_excerpt"), second.get("source_excerpt")])
    row["category"] = "composite_intent"
    row["composite_intent"] = True
    row["multi_document_complementary"] = True
    row["label_reason"] = f"复合查询由两个独立、已冻结且有来源定位的工程候选组合；ordinal={ordinal}。"
    return row


def add_composite_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positives = [row for row in rows if row.get("expected_chunk_ids") and not row.get("multi_document_complementary")]
    for index in range(11):
        first = positives[index]
        partner = positives[11 + index]
        replacement = union_row(first, partner, ordinal=index + 1)
        rows[rows.index(first)] = replacement

    prerequisite = next(row for row in rows if row.get("expected_intent") == "PREREQUISITE")
    verification = next(row for row in rows if row.get("expected_intent") == "VERIFICATION")
    procedures = [row for row in rows if row.get("expected_intent") == "PROCEDURE"]
    safety = [row for row in rows if row.get("expected_intent") == "SAFETY"]
    for index in range(4):
        sources = [procedures[index], prerequisite, safety[index], verification]
        row = deepcopy(procedures[index])
        row["query"] = (
            f"综合维护任务{index + 1}：操作前要满足什么条件和安全要求，"
            f"{procedures[index]['query'].rstrip('？?')}，完成后如何确认恢复？"
        )
        for key in ("expected_document_ids", "expected_chunk_ids", "expected_semantic_unit_ids"):
            row[key] = unique([value for source in sources for value in source.get(key) or []])
        row["source_locators"] = [source.get("source_locator") for source in sources if source.get("source_locator")]
        row["source_excerpts"] = unique([source.get("source_excerpt") for source in sources])
        row.update({
            "case_id": "",
            "category": "composite_intent",
            "expected_intent": "PROCEDURE",
            "composite_intent": True,
            "multi_document_complementary": True,
            "requires_clarification": False,
            "label_reason": "多证据操作任务同时请求前提、步骤、安全和完成验证，四项来源均有冻结定位。",
        })
        rows.append(row)
    return rows


def build_identity(
    row: dict[str, Any],
    mapping: dict[str, dict[str, Any]],
    chunk_locators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    semantic_ids = unique(row.get("expected_semantic_unit_ids") or [])
    chunk_ids = unique(row.get("expected_chunk_ids") or [])
    document_ids = unique(row.get("expected_document_ids") or [])
    mapped_chunks = unique([
        chunk_id
        for unit_id in semantic_ids
        for chunk_id in (mapping.get(unit_id) or {}).get("source_chunk_ids") or []
    ])
    # Keep hierarchy-aware semantic identities primary, but preserve any
    # explicitly labelled chunk that is not proven to be a source member of
    # those units. This prevents a multi-document label from collapsing into
    # one unit merely because an older artifact emitted only its first unit id.
    unmapped_chunks = [value for value in chunk_ids if value not in mapped_chunks]
    # A Semantic Unit and its source chunks are one evidence identity, not
    # several relevant items. Only complementary multi-document labels retain
    # the extra chunks that are not proven members of a labelled unit.
    direct = (
        unique([*semantic_ids, *unmapped_chunks])
        if row.get("multi_document_complementary")
        else (semantic_ids or chunk_ids)
    )
    supporting = unique([*mapped_chunks, *chunk_ids]) if semantic_ids else []
    locators = row.get("source_locators") or ([row.get("source_locator")] if row.get("source_locator") else [])
    if not locators:
        locators = [chunk_locators[value] for value in chunk_ids if chunk_locators.get(value)]
    sections = unique([
        section_id(document_ids[min(index, len(document_ids) - 1)], locator)
        for index, locator in enumerate(locators)
        if document_ids and locator
    ])
    grades = {value: 3 for value in direct}
    grades.update({value: max(2, grades.get(value, 0)) for value in supporting})
    return {
        "evaluation_level": "SEMANTIC_UNIT" if semantic_ids else "CHUNK",
        "expected_semantic_unit_ids": semantic_ids,
        "expected_chunk_ids": chunk_ids,
        "expected_section_ids": sections,
        "expected_document_ids": document_ids,
        "direct_evidence_ids": direct,
        "supporting_evidence_ids": [value for value in supporting if value not in direct],
        "background_evidence_ids": [],
        "source_locator": locators[0] if locators else {},
        "source_locators": locators,
        "relevance_grades": grades,
        "label_reason": row.get("label_reason") or "继承冻结的工程候选直接证据，并使用 Semantic Unit source mapping 证明层级对应。",
        "label_version": DATASET_VERSION,
    }


def main() -> None:
    if any((OUT / name).exists() for name in (
        "train_dev_dataset_v1.json", "dataset_manifest.json", "dataset_hash_manifest.json"
    )):
        raise SystemExit("R5-R5 Train/Dev v1 is immutable and already exists")
    if not SOURCE_DATASET.is_file():
        raise SystemExit("frozen R5-R4-MM source dataset is missing")
    source = json.loads(SOURCE_DATASET.read_text(encoding="utf-8"))
    rows = deepcopy(source["rows"])
    redundant_no_answer = [row for row in rows if row.get("category") == "no_answer"][3:]
    excluded = {row["case_id"] for row in redundant_no_answer}
    rows = [row for row in rows if row["case_id"] not in excluded]
    if len(rows) != 76:
        raise SystemExit(f"expected frozen calibrated source shape 76, got {len(rows)}")
    rows = add_composite_cases(rows)
    if len(rows) != TARGET_CASES:
        raise SystemExit(f"fixed dataset must contain {TARGET_CASES} cases, got {len(rows)}")

    mapping = semantic_mapping()
    chunk_locators = chunk_locator_mapping()
    normalized = []
    for index, source_row in enumerate(rows, start=1):
        row = deepcopy(source_row)
        requested = expected_requested_information(row["query"], str(row.get("expected_intent") or "GENERAL"))
        primary = expected_primary_intent(row["query"], requested, str(row.get("expected_intent") or "GENERAL"))
        row["case_id"] = f"r5r5-{index:03d}-" + hashlib.sha256(row["query"].encode("utf-8")).hexdigest()[:12]
        row["dataset_version"] = DATASET_VERSION
        row["label_version"] = DATASET_VERSION
        row["expected_primary_intent"] = primary
        row["expected_intent"] = primary
        row["expected_requested_information"] = requested
        row["composite_intent"] = bool(row.get("composite_intent") or len(requested) > 1)
        row["evaluation_identity"] = build_identity(row, mapping, chunk_locators)
        row["expected_semantic_unit_ids"] = row["evaluation_identity"]["expected_semantic_unit_ids"]
        row["expected_chunk_ids"] = row["evaluation_identity"]["expected_chunk_ids"]
        row["expected_document_ids"] = row["evaluation_identity"]["expected_document_ids"]
        row["expected_alarm_codes"] = [
            value for value in unique(row.get("expected_alarm_codes") or []) if value.upper() not in {"RS232", "RS485"}
        ]
        row["engineering_candidate"] = True
        row["expert_verified"] = False
        normalized.append(row)

    queries = [row["query"] for row in normalized]
    case_ids = [row["case_id"] for row in normalized]
    coverage = {
        "total": len(normalized),
        "exact_model": sum(bool(row.get("expected_device_models")) for row in normalized),
        "exact_alarm": sum(bool(row.get("expected_alarm_codes")) for row in normalized),
        "oral": sum(bool(row.get("oral")) for row in normalized),
        "vector_heavy": sum(bool(row.get("vector_heavy")) for row in normalized),
        "communication": sum("通信" in row["query"] or row.get("communication") for row in normalized),
        "cause": sum("CAUSE" in row["expected_requested_information"] for row in normalized),
        "action": sum("ACTION" in row["expected_requested_information"] for row in normalized),
        "safety": sum("SAFETY" in row["expected_requested_information"] for row in normalized),
        "prerequisite": sum("PREREQUISITE" in row["expected_requested_information"] for row in normalized),
        "verification": sum("VERIFICATION" in row["expected_requested_information"] for row in normalized),
        "composite_intent": sum(bool(row["composite_intent"]) for row in normalized),
        "no_answer": sum(bool(row.get("no_answer")) for row in normalized),
        "requires_clarification": sum(bool(row.get("requires_clarification")) for row in normalized),
        "context_merge": sum(bool(row.get("context_merge")) for row in normalized),
        "html_faq": sum(bool(row.get("html_faq")) for row in normalized),
        "pdf": sum(bool(row.get("pdf")) for row in normalized),
        "multi_document_complementary": sum(bool(row.get("multi_document_complementary")) for row in normalized),
        "entity_conflict": sum(bool(row.get("entity_conflict")) for row in normalized),
        "single_relevant": sum(len(row["evaluation_identity"]["direct_evidence_ids"]) == 1 for row in normalized),
        "multi_relevant": sum(len(row["evaluation_identity"]["direct_evidence_ids"]) >= 2 for row in normalized),
    }
    requirements = {
        "exact_model_at_least_8": coverage["exact_model"] >= 8,
        "exact_alarm_at_least_8": coverage["exact_alarm"] >= 8,
        "oral_at_least_16": coverage["oral"] >= 16,
        "vector_heavy_at_least_16": coverage["vector_heavy"] >= 16,
        "communication_at_least_8": coverage["communication"] >= 8,
        "cause_at_least_8": coverage["cause"] >= 8,
        "action_at_least_8": coverage["action"] >= 8,
        "safety_at_least_6": coverage["safety"] >= 6,
        "prerequisite_at_least_5": coverage["prerequisite"] >= 5,
        "verification_at_least_5": coverage["verification"] >= 5,
        "composite_at_least_12": coverage["composite_intent"] >= 12,
        "no_answer_at_least_8": coverage["no_answer"] >= 8,
        "clarification_at_least_8": coverage["requires_clarification"] >= 8,
        "context_at_least_8": coverage["context_merge"] >= 8,
        "html_at_least_5": coverage["html_faq"] >= 5,
        "pdf_at_least_12": coverage["pdf"] >= 12,
        "multi_document_at_least_6": coverage["multi_document_complementary"] >= 6,
        "entity_conflict_at_least_5": coverage["entity_conflict"] >= 5,
        "single_relevant_at_least_20": coverage["single_relevant"] >= 20,
        "multi_relevant_at_least_20": coverage["multi_relevant"] >= 20,
        "unique_queries": len(queries) == len(set(queries)),
        "unique_case_ids": len(case_ids) == len(set(case_ids)),
        "no_answer_expected_empty": all(
            not row["evaluation_identity"]["direct_evidence_ids"] for row in normalized if row.get("no_answer")
        ),
        "source_locator_present": all(
            row.get("no_answer")
            or row.get("requires_clarification")
            or bool(row["evaluation_identity"]["source_locator"])
            for row in normalized
        ),
        "expert_verified_zero": not any(row.get("expert_verified") for row in normalized),
    }
    failed = [name for name, passed in requirements.items() if not passed]
    if failed:
        missing_locators = [
            {
                "case_id": row["case_id"],
                "category": row.get("category"),
                "query": row["query"],
                "expected_document_ids": row.get("expected_document_ids") or [],
                "expected_chunk_ids": row.get("expected_chunk_ids") or [],
            }
            for row in normalized
            if not row.get("no_answer")
            and not row.get("requires_clarification")
            and not row["evaluation_identity"]["source_locator"]
        ]
        raise SystemExit(json.dumps({
            "coverage": coverage,
            "failed": failed,
            "missing_locator_case_ids": missing_locators,
        }, ensure_ascii=False))

    labels = [
        {
            "case_id": row["case_id"],
            "expected_primary_intent": row["expected_primary_intent"],
            "expected_requested_information": row["expected_requested_information"],
            "evaluation_identity": row["evaluation_identity"],
            "requires_clarification": bool(row.get("requires_clarification")),
            "no_answer": bool(row.get("no_answer")),
        }
        for row in normalized
    ]
    dataset_hash = sha256_json(normalized)
    label_hash = sha256_json(labels)
    payload = {
        "generated_at": now_iso(),
        "dataset_version": DATASET_VERSION,
        "case_count": TARGET_CASES,
        "dataset_hash": dataset_hash,
        "label_hash": label_hash,
        "source_dataset": ".runtime/task25b_r3_dev_r5_r4_mm/train_dev_dataset_v1.json",
        "source_dataset_sha256": sha256_file(SOURCE_DATASET),
        "source_formal_test_used": False,
        "immutable_after_creation": True,
        "coverage_manifest": coverage,
        "coverage_requirements": requirements,
        "anchor_matrix_version": ANCHOR_MATRIX_VERSION,
        "rerank_version": RERANK_VERSION,
        "rows": normalized,
    }
    dataset_path = write_once("train_dev_dataset_v1.json", payload)
    write_once("dataset_manifest.json", {
        "generated_at": payload["generated_at"],
        "dataset_version": DATASET_VERSION,
        "case_count": TARGET_CASES,
        "dataset_hash": dataset_hash,
        "label_hash": label_hash,
        "coverage_manifest": coverage,
        "coverage_requirements": requirements,
        "immutable": True,
        "formal_test_used": False,
    })
    write_once("dataset_hash_manifest.json", {
        "algorithm": "sha256",
        "dataset_version": DATASET_VERSION,
        "dataset_json_sha256": sha256_file(dataset_path),
        "canonical_rows_sha256": dataset_hash,
        "canonical_labels_sha256": label_hash,
        "iteration_contract": {
            "iteration_1_dataset_hash": dataset_hash,
            "iteration_2_dataset_hash": dataset_hash,
            "iteration_1_case_count": TARGET_CASES,
            "iteration_2_case_count": TARGET_CASES,
            "labels_mutable_after_iteration_start": False,
        },
    })
    print(json.dumps({
        "status": "R5_R5_TRAIN_DEV_V1_FROZEN",
        "dataset_version": DATASET_VERSION,
        "case_count": TARGET_CASES,
        "dataset_hash": dataset_hash,
        "label_hash": label_hash,
        "coverage": coverage,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
