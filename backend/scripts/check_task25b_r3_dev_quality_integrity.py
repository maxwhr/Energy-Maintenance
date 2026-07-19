from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalEvaluationCase,
    RetrievalEvaluationResult,
    RetrievalEvaluationRun,
)
from task25b_r3_dev_common import RUNTIME, now_iso, write_json


DATASET = "task25b_r2_u3_r3_dev_zh_v1"


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 3)


def _ranking_metrics(ranked: list[str], expected: list[str]) -> dict[str, float]:
    relevant = set(expected)
    if not relevant:
        correct = float(not ranked)
        return {"recall_at_5": correct, "recall_at_10": correct, "precision_at_3": correct,
                "precision_at_5": correct, "mrr": correct, "ndcg_at_10": correct, "map": correct}
    hits = [int(item in relevant) for item in ranked]
    recall = lambda k: sum(hits[:k]) / len(relevant)
    first = next((index + 1 for index, hit in enumerate(hits) if hit), None)
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits[:10]))
    idcg = sum(1 / math.log2(index + 2) for index in range(min(10, len(relevant)))) or 1
    precisions = [sum(hits[: index + 1]) / (index + 1) for index, hit in enumerate(hits) if hit]
    return {
        "recall_at_5": recall(5), "recall_at_10": recall(10),
        "precision_at_3": sum(hits[:3]) / 3, "precision_at_5": sum(hits[:5]) / 5,
        "mrr": 1 / first if first else 0.0, "ndcg_at_10": dcg / idcg,
        "map": sum(precisions) / len(relevant),
    }


def main() -> None:
    gate_path = RUNTIME / "chinese_pilot_quality_gate.json"
    if not gate_path.exists():
        raise SystemExit("QUALITY_GATE_INTERRUPTED: final quality gate artifact is missing")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    run_id = _uuid(gate.get("run_id"))
    if run_id is None:
        raise SystemExit("QUALITY_GATE_RESULT_INCONSISTENT: invalid run_id")

    with SessionLocal() as db:
        run = db.get(RetrievalEvaluationRun, run_id)
        if run is None:
            raise SystemExit("QUALITY_GATE_RESULT_INCONSISTENT: run not found")
        modes = list((run.retrieval_config_json or {}).get("modes") or [])
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET
        ).order_by(RetrievalEvaluationCase.id)))
        results = list(db.scalars(select(RetrievalEvaluationResult).where(
            RetrievalEvaluationResult.run_id == run_id
        ).order_by(RetrievalEvaluationResult.case_id, RetrievalEvaluationResult.retrieval_mode)))
        sibling_runs = list(db.scalars(select(RetrievalEvaluationRun).where(
            RetrievalEvaluationRun.dataset_version == DATASET
        ).order_by(RetrievalEvaluationRun.created_at)))

        case_by_id = {str(item.id): item for item in cases}
        actual_keys = [(str(item.case_id), item.retrieval_mode) for item in results]
        counts = Counter(actual_keys)
        expected_keys = {(str(case.id), mode) for case in cases for mode in modes}
        missing = sorted(expected_keys - set(actual_keys))
        duplicates = sorted((case_id, mode, count) for (case_id, mode), count in counts.items() if count > 1)

        chunk_ids = {_uuid(value) for item in results for value in (item.ranked_chunk_ids or [])}
        chunk_ids.discard(None)
        doc_ids = {_uuid(value) for item in results for value in (item.ranked_document_ids or [])}
        doc_ids.discard(None)
        chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))) if chunk_ids else []
        doc_ids.update(item.document_id for item in chunks)
        documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids)))) if doc_ids else []
        chunk_by_id = {str(item.id): item for item in chunks}
        doc_by_id = {str(item.id): item for item in documents}

        mode_rows: dict[str, list[dict]] = defaultdict(list)
        for result in results:
            case = case_by_id.get(str(result.case_id))
            if case is None:
                continue
            ranked = [str(value) for value in (result.ranked_chunk_ids or result.ranked_document_ids or result.ranked_media_ids or [])]
            expected = [str(value) for value in (case.expected_chunk_ids or case.expected_document_ids or case.expected_media_ids or [])]
            cited_docs: list[KnowledgeDocument] = []
            unresolved = 0
            for value in ranked:
                chunk = chunk_by_id.get(value)
                document = doc_by_id.get(str(chunk.document_id)) if chunk else doc_by_id.get(value)
                if document is None:
                    unresolved += 1
                else:
                    cited_docs.append(document)
            languages = [(item.metadata_json or {}).get("normalized_language") for item in cited_docs]
            english_leak = any(language == "en" for language in languages)
            non_chinese_leak = any(language != "zh-CN" for language in languages)
            pending_leak = any(item.review_status != "approved" for item in cited_docs)
            marketing_leak = any(bool((item.metadata_json or {}).get("marketing_only")) or
                                 (item.metadata_json or {}).get("quality_status") == "MARKETING_ONLY" for item in cited_docs)
            superseded_leak = any(item.status != "active" or bool((item.metadata_json or {}).get("superseded_by_document_id"))
                                  for item in cited_docs)
            citation_valid = not unresolved and not non_chinese_leak and not pending_leak and not marketing_leak and not superseded_leak
            metrics = _ranking_metrics(ranked, expected)
            metrics.update({
                "citation_valid": float(citation_valid),
                "citation_covered": float(bool(ranked) and citation_valid) if case.category != "no_answer" else 1.0,
                "english_leakage": float(english_leak), "non_chinese_leakage": float(non_chinese_leak),
                "pending_leakage": float(pending_leak),
                "marketing_leakage": float(marketing_leak), "superseded_leakage": float(superseded_leak),
                "latency_ms": float(result.latency_ms), "fallback": float(result.fallback_used),
                "error": float(bool(result.error_summary)),
                "timeout": float("timeout" in (result.error_summary or "").lower()),
                "no_answer_actual": case.category == "no_answer", "no_answer_predicted": not ranked,
                "model_case": case.category == "device_model_query", "fault_case": case.category == "fault_code_query",
                "top1_expected": bool(ranked and ranked[0] in set(expected)),
            })
            mode_rows[result.retrieval_mode].append(metrics)

        by_mode: dict[str, dict] = {}
        for mode in modes:
            rows = mode_rows.get(mode, [])
            aggregate = {key: round(statistics.fmean(row[key] for row in rows), 6) if rows else 0.0 for key in (
                "recall_at_5", "recall_at_10", "precision_at_3", "precision_at_5", "mrr", "ndcg_at_10", "map",
                "citation_valid", "citation_covered", "english_leakage", "non_chinese_leakage",
                "pending_leakage", "marketing_leakage",
                "superseded_leakage", "fallback", "timeout", "error",
            )}
            tp = sum(row["no_answer_actual"] and row["no_answer_predicted"] for row in rows)
            fp = sum((not row["no_answer_actual"]) and row["no_answer_predicted"] for row in rows)
            fn = sum(row["no_answer_actual"] and (not row["no_answer_predicted"]) for row in rows)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            aggregate.update({
                "no_answer_precision": round(precision, 6), "no_answer_recall": round(recall, 6),
                "no_answer_f1": round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0,
                "model_accuracy": round(statistics.fmean(row["top1_expected"] for row in rows if row["model_case"]), 6),
                "alarm_fault_accuracy": round(statistics.fmean(row["top1_expected"] for row in rows if row["fault_case"]), 6),
                "p50_ms": _percentile([row["latency_ms"] for row in rows], .50),
                "p95_ms": _percentile([row["latency_ms"] for row in rows], .95),
                "p99_ms": _percentile([row["latency_ms"] for row in rows], .99),
                "result_count": len(rows),
            })
            by_mode[mode] = aggregate

        preferred = by_mode.get("adaptive", {})
        checks = {
            "recall_at_5": preferred.get("recall_at_5", 0) >= .80,
            "recall_at_10": preferred.get("recall_at_10", 0) >= .90,
            "mrr": preferred.get("mrr", 0) >= .75,
            "ndcg_at_10": preferred.get("ndcg_at_10", 0) >= .80,
            "precision_at_5": preferred.get("precision_at_5", 0) >= .45,
            "citation_validity": preferred.get("citation_valid", 0) >= .98,
            "citation_coverage": preferred.get("citation_covered", 0) >= .95,
            "no_answer_f1": preferred.get("no_answer_f1", 0) >= .85,
            "model_accuracy": preferred.get("model_accuracy", 0) == 1.0,
            "english_leakage": preferred.get("english_leakage", 1) == 0,
            "non_chinese_leakage": preferred.get("non_chinese_leakage", 1) == 0,
            "pending_leakage": preferred.get("pending_leakage", 1) == 0,
            "marketing_leakage": preferred.get("marketing_leakage", 1) == 0,
            "superseded_leakage": preferred.get("superseded_leakage", 1) == 0,
            "warm_p95": preferred.get("p95_ms", math.inf) <= 3500,
            "error_rate": preferred.get("error", 1) == 0,
        }
        mojibake_markers = ("銆", "锛", "鈥", "€", "鏄", "绂")
        encoding_issue_cases = [str(item.id) for item in cases if any(marker in item.query_text for marker in mojibake_markers)]
        integrity = {
            "generated_at": now_iso(), "recovery_status": "QUALITY_GATE_COMPLETED",
            "run_id": str(run.id), "run_status": run.run_status, "started_at": run.started_at,
            "completed_at": run.completed_at, "dataset_version": run.dataset_version,
            "collection": run.collection_name, "partition": "pilot_r2",
            "embedding_model": run.embedding_model, "embedding_dimension": run.embedding_dimension,
            "cases": len(cases), "modes": modes, "expected_results": len(expected_keys),
            "actual_results": len(results), "missing_count": len(missing), "duplicate_count": len(duplicates),
            "error_count": sum(bool(item.error_summary) for item in results),
            "sibling_run_count": len(sibling_runs),
            "sibling_runs": [{"run_id": str(item.id), "status": item.run_status, "created_at": item.created_at} for item in sibling_runs],
            "benchmark_encoding_issue_case_count": len(encoding_issue_cases),
            "benchmark_encoding_issue_case_ids": encoding_issue_cases,
            "by_mode": by_mode, "checks": checks,
            "quality_gate": "DEVELOPMENT_ENGINEERING_PILOT_PASS" if all(checks.values()) else "DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED",
            "complete": len(results) == len(expected_keys) and not missing and not duplicates and run.run_status == "succeeded",
            "expert_validated": False,
        }

    write_json("missing_case_modes.json", {"generated_at": now_iso(), "run_id": str(run_id), "count": len(missing),
                                             "items": [{"case_id": case_id, "mode": mode} for case_id, mode in missing]})
    write_json("duplicate_case_modes.json", {"generated_at": now_iso(), "run_id": str(run_id), "count": len(duplicates),
                                               "items": [{"case_id": case_id, "mode": mode, "count": count}
                                                         for case_id, mode, count in duplicates]})
    write_json("quality_gate_integrity.json", integrity)
    print(json.dumps({"status": integrity["recovery_status"], "complete": integrity["complete"],
                      "actual_results": integrity["actual_results"], "quality_gate": integrity["quality_gate"],
                      "benchmark_encoding_issue_case_count": integrity["benchmark_encoding_issue_case_count"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
