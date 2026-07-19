from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r2"
V2_DATASET = "task25b_r3_dev_r1_zh_v2"
V2_RUN_ID = "3e40e25f-f1f1-4146-9e1e-629d2ce76045"
V3_DATASET = "task25b_r3_dev_r2_zh_v3"
V3_FREEZE = "task25b_r3_dev_r2_zh_v3_test_v3"
V3_PURPOSE = "task25b_r3_dev_r2_zh_quality_gate_v3"
MODES = ("keyword", "vector", "hybrid", "adaptive")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p) - 1))]


def normalized_text(value: str | None) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())


def section_key(chunk: KnowledgeChunk | None, document: KnowledgeDocument | None) -> str:
    if chunk is None:
        return "missing"
    metadata = chunk.metadata_json or {}
    locator = metadata.get("heading_path") or metadata.get("source_locator") or chunk.section_title
    if not locator:
        locator = f"page:{chunk.page_number or 'unknown'}"
    return f"{document.id if document else chunk.document_id}:{normalized_text(str(locator))}"


def relevance_sets(
    case: RetrievalEvaluationCase,
    chunks: dict[str, KnowledgeChunk],
    documents: dict[str, KnowledgeDocument],
) -> dict[str, set[str]]:
    expected_chunks = {str(value) for value in (case.expected_chunk_ids or []) if str(value) in chunks}
    expected_documents = {str(value) for value in (case.expected_document_ids or [])}
    expected_documents.update(str(chunks[value].document_id) for value in expected_chunks)
    expected_sections = {
        section_key(chunks.get(value), documents.get(str(chunks[value].document_id)))
        for value in expected_chunks
    }
    return {"chunks": expected_chunks, "documents": expected_documents, "sections": expected_sections}


def rank_metrics(ranked: list[str], relevant: set[str], *, k: int = 5) -> dict[str, float | int | None]:
    if not relevant:
        abstained = not ranked
        return {"hit_at_1": float(abstained), "hit_at_5": float(abstained), "reciprocal_rank": float(abstained),
                "precision_at_5": float(abstained), "r_precision": float(abstained), "recall_at_5": float(abstained),
                "recall_at_10": float(abstained), "ndcg_at_10": float(abstained),
                "first_rank": None}
    hits = [item in relevant for item in ranked]
    first = next((index + 1 for index, hit in enumerate(hits) if hit), None)
    top5 = hits[:k]
    r = len(relevant)
    dcg = sum(float(hit) / math.log2(index + 2) for index, hit in enumerate(hits[:10]))
    idcg = sum(1.0 / math.log2(index + 2) for index in range(min(10, r))) or 1.0
    return {
        "hit_at_1": float(bool(hits[:1] and hits[0])),
        "hit_at_5": float(any(top5)),
        "reciprocal_rank": 1.0 / first if first else 0.0,
        "precision_at_5": sum(top5) / k,
        "r_precision": sum(hits[:r]) / r,
        "recall_at_5": min(1.0, sum(top5) / r),
        "recall_at_10": min(1.0, sum(hits[:10]) / r),
        "ndcg_at_10": dcg / idcg,
        "first_rank": first,
    }


def jaccard(left: list[str], right: list[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def kendall_like(left: list[str], right: list[str], *, k: int = 5) -> float | None:
    common = [value for value in left[:k] if value in set(right[:k])]
    if len(common) < 2:
        return None
    left_pos = {value: index for index, value in enumerate(left[:k])}
    right_pos = {value: index for index, value in enumerate(right[:k])}
    pairs = 0
    concordant = 0
    for index, first in enumerate(common):
        for second in common[index + 1:]:
            pairs += 1
            concordant += int((left_pos[first] - left_pos[second]) * (right_pos[first] - right_pos[second]) > 0)
    return (2 * concordant - pairs) / pairs if pairs else None


def coverage_rows(cases: list[RetrievalEvaluationCase]) -> dict[str, int]:
    def count(flag: str) -> int:
        return sum(bool((case.metadata_json or {}).get(flag)) for case in cases)
    return {
        "total": len(cases),
        "model_cases": count("is_model_case"), "alarm_cases": count("is_alarm_case"),
        "vector_heavy": count("is_vector_heavy"), "no_answer": count("is_no_answer"),
        "multi_relevant": sum(int((case.metadata_json or {}).get("relevance_cardinality") or 0) > 1 for case in cases),
        "single_relevant": sum(int((case.metadata_json or {}).get("relevance_cardinality") or 0) == 1 for case in cases),
    }


def counter_dict(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))
