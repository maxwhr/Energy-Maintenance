from __future__ import annotations

import csv
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from task25b_r3_dev_r3_common import OUT, R2_DATASET, jaccard, masked_preview, normalized, now_iso, terms, text_hash, write_json


ALARM_RE = r"\b(?:[A-Z]{1,4}\d{3,6}|\d{4,6})\b"
MODEL_RE = r"\b(?:SUN|LUNA|SMARTLOGGER)[A-Z0-9-]{3,}\b"
GROUNDED_DATASET = "task25b_r3_dev_r3_grounded_train_dev_v1"
COMPONENT_SOURCE_TERMS = {
    "通信链路": ("通信", "rs485", "modbus", "以太网", "网线", "网络", "地址"),
    "直流侧与组串": ("直流", "组串", "光伏", "mc4", "绝缘"),
    "交流侧与电网": ("交流", "电网", "并网", "电压", "频率"),
    "散热与风扇": ("风扇", "散热", "温度", "过温"),
    "储能连接": ("电池", "储能", "bat", "soc"),
    "接地与防护": ("接地", "防护", "触电", "危险", "警告", "安全"),
    "安装与接线": ("安装", "接线", "端子", "线缆", "连接器"),
}
ACTION_SOURCE_TERMS = {
    "检查": ("检查", "核查", "确认"), "测量": ("测量", "检测", "测试"),
    "设置": ("设置", "配置", "参数"), "隔离": ("断开", "隔离", "关机", "禁止"),
    "更换或修复": ("更换", "紧固", "清洁", "修复"),
}


def _source_locator(chunk: KnowledgeChunk) -> dict:
    metadata = chunk.metadata_json or {}
    return {
        "page_number": chunk.page_number,
        "section_title": chunk.section_title,
        "heading_path": metadata.get("heading_path") or metadata.get("section_path"),
    }


def _has_full_anchor(query: str) -> tuple[bool, bool]:
    upper = query.upper()
    return bool(__import__("re").search(MODEL_RE, upper)), bool(__import__("re").search(ALARM_RE, upper))


def _nearest_chunk(
    expected: KnowledgeChunk,
    chunks: list[KnowledgeChunk],
    query_terms: set[str],
) -> tuple[KnowledgeChunk | None, float]:
    candidates = [
        chunk for chunk in chunks
        if chunk.document_id == expected.document_id and abs(chunk.chunk_index - expected.chunk_index) <= 2 and chunk.id != expected.id
    ]
    if not candidates:
        return None, 0.0
    best = max(candidates, key=lambda chunk: jaccard(query_terms, terms(chunk.content)))
    return best, jaccard(query_terms, terms(best.content))


def _classify(
    *, case: RetrievalEvaluationCase, expected: KnowledgeChunk | None, document: KnowledgeDocument | None,
    all_chunks: list[KnowledgeChunk],
) -> tuple[str, str, dict]:
    metadata = case.metadata_json or {}
    query = case.query_text
    query_terms = terms(query)
    model_anchor, alarm_anchor = _has_full_anchor(query)
    if not bool(metadata.get("is_vector_heavy")):
        return "NOT_VECTOR_HEAVY", "case_not_declared_vector_heavy", {"model": model_anchor, "alarm": alarm_anchor}
    if bool(metadata.get("is_no_answer")):
        return "NOT_VECTOR_HEAVY", "no_answer_cannot_be_positive_vector_heavy_pair", {"model": model_anchor, "alarm": alarm_anchor}
    if expected is None or document is None:
        return "WRONG_EXPECTED_CHUNK", "expected_chunk_or_document_missing", {"model": model_anchor, "alarm": alarm_anchor}
    evidence = metadata.get("grounding_evidence") or {}
    if evidence:
        same_source = str(evidence.get("source_chunk_id")) == str(expected.id)
        source_hash_matches = evidence.get("source_content_hash") == text_hash(expected.content)
        components = [str(value) for value in (evidence.get("components") or [])]
        actions = [str(value) for value in (evidence.get("actions") or [])]
        source_lower = expected.content.lower()
        facts_in_source = all(any(needle in source_lower for needle in COMPONENT_SOURCE_TERMS.get(value, ())) for value in components)
        facts_in_source = facts_in_source and all(any(needle in source_lower for needle in ACTION_SOURCE_TERMS.get(value, ())) for value in actions)
        facts_in_query = all(normalized(value) in normalized(query) for value in [*components[:1], *actions[:1]])
        if same_source and source_hash_matches and components and actions and facts_in_source and facts_in_query and not (model_anchor or alarm_anchor):
            return "GROUNDED_STRONG", "deterministic_source_evidence_matches_query_and_expected_chunk", {
                "content_overlap": 0.0, "title_overlap": 0.0, "heading_overlap": 0.0,
                "nearby_overlap": 0.0, "nearby_chunk_id": None, "model": False, "alarm": False,
            }
        return "GROUNDING_WEAK", "grounding_evidence_does_not_reproduce_from_expected_source", {
            "content_overlap": 0.0, "title_overlap": 0.0, "heading_overlap": 0.0,
            "nearby_overlap": 0.0, "nearby_chunk_id": None, "model": model_anchor, "alarm": alarm_anchor,
        }
    content_overlap = jaccard(query_terms, terms(expected.content))
    title_overlap = jaccard(query_terms, terms(document.title))
    heading_overlap = jaccard(query_terms, terms(expected.section_title))
    nearby, nearby_overlap = _nearest_chunk(expected, all_chunks, query_terms)
    direct_evidence = max(content_overlap, title_overlap, heading_overlap)
    # A full identifier makes the case lexical by definition, not a semantic-vector probe.
    if model_anchor or alarm_anchor:
        return "NOT_VECTOR_HEAVY", "query_contains_complete_model_or_alarm_anchor", {
            "content_overlap": content_overlap, "title_overlap": title_overlap, "heading_overlap": heading_overlap,
            "nearby_overlap": nearby_overlap, "nearby_chunk_id": str(nearby.id) if nearby else None,
            "model": model_anchor, "alarm": alarm_anchor,
        }
    if nearby and nearby_overlap >= direct_evidence + 0.12 and nearby_overlap >= 0.08:
        return "AMBIGUOUS_SECTION", "adjacent_chunk_has_stronger_query_evidence", {
            "content_overlap": content_overlap, "title_overlap": title_overlap, "heading_overlap": heading_overlap,
            "nearby_overlap": nearby_overlap, "nearby_chunk_id": str(nearby.id), "model": model_anchor, "alarm": alarm_anchor,
        }
    if direct_evidence < 0.025:
        return "GROUNDING_WEAK", "query_and_expected_chunk_have_insufficient_source_evidence", {
            "content_overlap": content_overlap, "title_overlap": title_overlap, "heading_overlap": heading_overlap,
            "nearby_overlap": nearby_overlap, "nearby_chunk_id": str(nearby.id) if nearby else None,
            "model": model_anchor, "alarm": alarm_anchor,
        }
    if direct_evidence < 0.09:
        return "GROUNDED_MODERATE", "source_evidence_is_present_but_indirect", {
            "content_overlap": content_overlap, "title_overlap": title_overlap, "heading_overlap": heading_overlap,
            "nearby_overlap": nearby_overlap, "nearby_chunk_id": str(nearby.id) if nearby else None,
            "model": model_anchor, "alarm": alarm_anchor,
        }
    return "GROUNDED_STRONG", "expected_chunk_directly_supports_query_terms", {
        "content_overlap": content_overlap, "title_overlap": title_overlap, "heading_overlap": heading_overlap,
        "nearby_overlap": nearby_overlap, "nearby_chunk_id": str(nearby.id) if nearby else None,
        "model": model_anchor, "alarm": alarm_anchor,
    }


def main() -> None:
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string().in_((R2_DATASET, GROUNDED_DATASET)),
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
            RetrievalEvaluationCase.metadata_json["is_vector_heavy"].as_boolean().is_(True),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name)))
        expected_ids = {str(value) for case in cases for value in (case.expected_chunk_ids or [])}
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(expected_ids)))} if expected_ids else {}
        document_ids = {chunk.document_id for chunk in chunks.values()}
        documents = {chunk.id: chunk for chunk in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))} if document_ids else {}
        all_chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id.in_(document_ids)))) if document_ids else []
        rows = []
        for case in cases:
            expected_id = str((case.expected_chunk_ids or [""])[0])
            expected = chunks.get(expected_id)
            document = documents.get(expected.document_id) if expected else None
            status, reason, details = _classify(case=case, expected=expected, document=document, all_chunks=all_chunks)
            metadata = case.metadata_json or {}
            rows.append({
                "case_id": str(case.id), "dataset": (case.metadata_json or {}).get("dataset_version"), "split": case.dataset_split, "query_text_hash": text_hash(case.query_text),
                "query_text_masked_preview": masked_preview(case.query_text),
                "expected_document_ids": [str(value) for value in (case.expected_document_ids or [])],
                "expected_section_ids": [str((expected.metadata_json or {}).get("heading_path") or (expected.metadata_json or {}).get("section_path") or expected.section_title)] if expected else [],
                "expected_chunk_ids": [str(value) for value in (case.expected_chunk_ids or [])],
                "source_locator": _source_locator(expected) if expected else None,
                "source_excerpt_hash": text_hash(expected.content) if expected else None,
                "query_type": case.category, "lexical_overlap": round(details.get("content_overlap", 0.0), 6),
                "title_overlap": round(details.get("title_overlap", 0.0), 6), "heading_overlap": round(details.get("heading_overlap", 0.0), 6),
                "model_anchor_present": bool(details.get("model")), "alarm_code_present": bool(details.get("alarm")),
                "alarm_name_present": bool(metadata.get("alarm_name")),
                "expected_evidence_strength": round(max(details.get("content_overlap", 0.0), details.get("title_overlap", 0.0), details.get("heading_overlap", 0.0)), 6),
                "grounding_status": status, "grounding_reason": reason,
                "adjacent_chunk_id": details.get("nearby_chunk_id"), "adjacent_overlap": round(details.get("nearby_overlap", 0.0), 6),
                "raw_query_not_exported": True, "test_v3_used": False,
            })
    # A source-derived query is not chunk-grounded when the same deterministic semantic
    # signature labels several unrelated source chunks.  Keep the evidence but mark it
    # ambiguous rather than allowing a one-of-many chunk label into Canary.
    signatures = Counter()
    for case in cases:
        metadata = case.metadata_json or {}
        evidence = metadata.get("grounding_evidence") or {}
        if metadata.get("dataset_version") == GROUNDED_DATASET:
            signatures[(tuple(evidence.get("components") or []), tuple(evidence.get("actions") or []), tuple(evidence.get("themes") or []))] += 1
    by_case = {str(case.id): case for case in cases}
    for row in rows:
        case = by_case[row["case_id"]]
        evidence = ((case.metadata_json or {}).get("grounding_evidence") or {})
        signature = (tuple(evidence.get("components") or []), tuple(evidence.get("actions") or []), tuple(evidence.get("themes") or []))
        row["semantic_signature_count"] = signatures.get(signature, 0)
        if row["grounding_status"] == "GROUNDED_STRONG" and signatures.get(signature, 0) > 1:
            row["grounding_status"] = "AMBIGUOUS_SECTION"
            row["grounding_reason"] = "same_semantic_signature_labels_multiple_source_chunks"
    summary = Counter(row["grounding_status"] for row in rows)
    payload = {"generated_at": now_iso(), "datasets": [R2_DATASET, GROUNDED_DATASET], "splits": ["train", "dev"], "test_v3_used": False,
               "cases_reviewed": len(rows), "summary": dict(sorted(summary.items())), "rows": rows,
               "usable_canary_cases": sum(row["grounding_status"] in {"GROUNDED_STRONG", "GROUNDED_MODERATE"} for row in rows)}
    write_json("vector_heavy_grounding.json", payload)
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["case_id", "grounding_status"]
    with (OUT / "vector_heavy_grounding.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: __import__("json").dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    print(__import__("json").dumps({"status": "PASSED", "cases": len(rows), "summary": payload["summary"], "usable_canary_cases": payload["usable_canary_cases"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
