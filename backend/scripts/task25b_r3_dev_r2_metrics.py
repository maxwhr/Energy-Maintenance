from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Any

from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.services.query_understanding_service import QueryUnderstandingService, normalize_alarm_identifier, normalize_device_model
from task25b_r3_dev_r2_common import percentile, rank_metrics, relevance_sets, section_key


def raw_ids(diagnostics: dict[str, Any]) -> list[str]:
    return [str(item.get("chunk_id")) for item in (diagnostics.get("raw_results") or []) if item.get("chunk_id")]


def candidate_ids(diagnostics: dict[str, Any], mode: str) -> list[str]:
    return [str(value) for value in (diagnostics.get(f"{mode}_candidate_ids") or [])]


def _model_in_chunk(chunk: KnowledgeChunk | None, document: KnowledgeDocument | None, model: str) -> bool:
    expected = normalize_device_model(model)
    if not expected or not chunk or not document:
        return False
    content = " ".join((document.title or "", document.product_series or "", document.model or "", chunk.section_title or "", chunk.content or "",
                        " ".join(str(value) for value in ((document.metadata_json or {}).get("device_models") or []))))
    return expected in normalize_device_model(content)


def _alarm_in_chunk(chunk: KnowledgeChunk | None, alarm: str) -> bool:
    expected = normalize_alarm_identifier(alarm)
    if not expected or not chunk:
        return False
    content = " ".join((chunk.section_title or "", chunk.content or "", " ".join(str(value) for value in ((chunk.metadata_json or {}).get("fault_codes") or []))))
    return expected in normalize_alarm_identifier(content)


def metric_row(
    *, case: RetrievalEvaluationCase, mode: str, surfaced_ids: list[str], diagnostics: dict[str, Any],
    chunks: dict[str, KnowledgeChunk], documents: dict[str, KnowledgeDocument], error: bool = False,
) -> dict[str, Any]:
    relevance = relevance_sets(case, chunks, documents)
    raw = raw_ids(diagnostics)
    raw_metrics = rank_metrics(raw, relevance["chunks"])
    surfaced_metrics = rank_metrics(surfaced_ids, relevance["chunks"])
    doc_surfaced = [str(chunks[value].document_id) for value in surfaced_ids if value in chunks]
    section_surfaced = [section_key(chunks.get(value), documents.get(str(chunks[value].document_id))) for value in surfaced_ids if value in chunks]
    metadata = case.metadata_json or {}
    top_chunk = chunks.get(surfaced_ids[0]) if surfaced_ids else None
    top_document = documents.get(str(top_chunk.document_id)) if top_chunk else None
    query = QueryUnderstandingService().understand(case.query_text)
    required_model = str(metadata.get("required_model") or "")
    required_alarm = str(metadata.get("required_alarm_identifier") or "")
    returned = len(surfaced_ids)
    irrelevant = sum(value not in relevance["chunks"] for value in surfaced_ids)
    return {
        "case_id": str(case.id), "mode": mode, "category": case.category,
        "is_no_answer": bool(metadata.get("is_no_answer")), "is_model_case": bool(metadata.get("is_model_case")),
        "is_alarm_case": bool(metadata.get("is_alarm_case")), "is_vector_heavy": bool(metadata.get("is_vector_heavy")),
        "relevance_cardinality": int(metadata.get("relevance_cardinality") or len(relevance["chunks"])),
        "raw_ids": raw, "surfaced_ids": surfaced_ids, "raw_metrics": raw_metrics, "surfaced_metrics": surfaced_metrics,
        "document_metrics": rank_metrics(doc_surfaced, relevance["documents"]),
        "section_metrics": rank_metrics(section_surfaced, relevance["sections"]),
        "returned_result_count": returned, "surfaced_precision": (returned - irrelevant) / returned if returned else float(not relevance["chunks"]),
        "surfaced_recall": len({value for value in surfaced_ids if value in relevance["chunks"]}) / len(relevance["chunks"]) if relevance["chunks"] else float(not surfaced_ids),
        "irrelevant_result_rate": irrelevant / returned if returned else 0.0,
        "citation_valid": float(bool(diagnostics.get("citation_valid"))), "citation_coverage": float(diagnostics.get("citation_coverage") or 0.0),
        "scope_valid": bool(diagnostics.get("scope_validation_passed")), "fallback": bool(diagnostics.get("fallback_used")),
        "actual_route": diagnostics.get("actual_route"), "external_calls": diagnostics.get("external_call_counts") or {},
        "latency_ms": float((diagnostics.get("stage_latency") or {}).get("total_ms") or 0.0),
        "error": bool(error), "vector_candidate_recall_at_50": len(set(candidate_ids(diagnostics, "vector")[:50]) & relevance["chunks"]) / len(relevance["chunks"]) if relevance["chunks"] else 1.0,
        "query_model_extraction": normalize_device_model(required_model) in {normalize_device_model(value) for value in query.device_models} if required_model else None,
        "retrieved_model_consistency": _model_in_chunk(top_chunk, top_document, required_model) if required_model else None,
        "exact_model_filter": _model_in_chunk(top_chunk, top_document, required_model) if required_model else None,
        "query_alarm_extraction": normalize_alarm_identifier(required_alarm) in {normalize_alarm_identifier(value) for value in query.fault_codes} if required_alarm else None,
        "retrieved_alarm_consistency": _alarm_in_chunk(top_chunk, required_alarm) if required_alarm else None,
        "exact_alarm_filter": _alarm_in_chunk(top_chunk, required_alarm) if required_alarm else None,
    }


def _mean(rows: list[dict[str, Any]], getter, *, default: float | None = 0.0) -> float | None:
    values = [getter(row) for row in rows]
    values = [float(value) for value in values if value is not None]
    return round(fmean(values), 6) if values else default


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    output["hit_at_1"] = _mean(rows, lambda row: row["surfaced_metrics"]["hit_at_1"])
    output["hit_at_5"] = _mean(rows, lambda row: row["surfaced_metrics"]["hit_at_5"])
    output["recall_at_5"] = _mean(rows, lambda row: row["raw_metrics"]["recall_at_5"])
    output["recall_at_10"] = _mean(rows, lambda row: row["raw_metrics"]["recall_at_10"])
    output["mrr"] = _mean(rows, lambda row: row["raw_metrics"]["reciprocal_rank"])
    output["ndcg_at_10"] = _mean(rows, lambda row: row["raw_metrics"]["ndcg_at_10"])
    output["raw_precision_at_5"] = _mean(rows, lambda row: row["raw_metrics"]["precision_at_5"])
    output["surfaced_precision"] = _mean(rows, lambda row: row["surfaced_precision"])
    output["surfaced_recall"] = _mean(rows, lambda row: row["surfaced_recall"])
    output["surfaced_irrelevant_rate"] = _mean(rows, lambda row: row["irrelevant_result_rate"])
    output["citation_validity"] = _mean(rows, lambda row: row["citation_valid"])
    output["citation_coverage"] = _mean(rows, lambda row: row["citation_coverage"])
    output["leakage"] = _mean(rows, lambda row: float(not row["scope_valid"]))
    output["error_rate"] = _mean(rows, lambda row: float(row["error"]))
    output["p95_ms"] = round(percentile([row["latency_ms"] for row in rows], .95), 3)
    output["p50_ms"] = round(percentile([row["latency_ms"] for row in rows], .50), 3)
    output["no_answer_f1"] = no_answer_f1(rows)
    output["model"] = applicability(rows, "model")
    output["alarm"] = applicability(rows, "alarm")
    multi = [row for row in rows if row["relevance_cardinality"] > 1]
    single = [row for row in rows if row["relevance_cardinality"] == 1]
    output["multi_relevant"] = {"cases": len(multi), "precision_at_5": _mean(multi, lambda row: row["raw_metrics"]["precision_at_5"]),
                                "r_precision": _mean(multi, lambda row: row["raw_metrics"]["r_precision"]), "recall_at_5": _mean(multi, lambda row: row["raw_metrics"]["recall_at_5"])}
    output["single_relevant"] = {"cases": len(single), "hit_at_1": _mean(single, lambda row: row["surfaced_metrics"]["hit_at_1"]),
                                  "hit_at_5": _mean(single, lambda row: row["surfaced_metrics"]["hit_at_5"]), "mrr": _mean(single, lambda row: row["raw_metrics"]["reciprocal_rank"])}
    return output


def applicability(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    prefix = "model" if kind == "model" else "alarm"
    selected = [row for row in rows if row[f"is_{prefix}_case"]]
    if not selected:
        return {"coverage": 0, "applicable": False, "query_extraction": None, "retrieved_consistency": None, "exact_filter": None}
    return {"coverage": len(selected), "applicable": True,
            "query_extraction": _mean(selected, lambda row: row[f"query_{prefix}_extraction"], default=None),
            "retrieved_consistency": _mean(selected, lambda row: row[f"retrieved_{prefix}_consistency"], default=None),
            "exact_filter": _mean(selected, lambda row: row[f"exact_{prefix}_filter"], default=None)}


def no_answer_f1(rows: list[dict[str, Any]]) -> float:
    selected = [row for row in rows if row["is_no_answer"]]
    if not selected:
        return 0.0
    tp = sum(not row["surfaced_ids"] for row in selected)
    fn = len(selected) - tp
    fp = sum(not row["is_no_answer"] and not row["surfaced_ids"] for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0


def vector_heavy(rows_by_mode: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    subset = {mode: [row for row in rows if row["is_vector_heavy"]] for mode, rows in rows_by_mode.items()}
    keyword = aggregate(subset.get("keyword", [])) if subset.get("keyword") else {}
    adaptive = aggregate(subset.get("adaptive", [])) if subset.get("adaptive") else {}
    vector = aggregate(subset.get("vector", [])) if subset.get("vector") else {}
    adaptive_routes = Counter(row["actual_route"] or "unknown" for row in subset.get("adaptive", []))
    return {"cases": len(subset.get("adaptive", [])), "keyword_recall_at_5": keyword.get("recall_at_5", 0.0),
            "vector_recall_at_5": vector.get("recall_at_5", 0.0), "adaptive_recall_at_5": adaptive.get("recall_at_5", 0.0),
            "keyword_ndcg": keyword.get("ndcg_at_10", 0.0), "adaptive_ndcg": adaptive.get("ndcg_at_10", 0.0),
            "adaptive_mrr": adaptive.get("mrr", 0.0), "vector_candidate_recall_at_50": _mean(subset.get("vector", []), lambda row: row["vector_candidate_recall_at_50"]),
            "adaptive_routes": dict(adaptive_routes),
            "relative_recall_gain": round((adaptive.get("recall_at_5", 0.0) or 0.0) - (keyword.get("recall_at_5", 0.0) or 0.0), 6),
            "relative_ndcg_gain": round((adaptive.get("ndcg_at_10", 0.0) or 0.0) - (keyword.get("ndcg_at_10", 0.0) or 0.0), 6)}


from collections import Counter  # noqa: E402
