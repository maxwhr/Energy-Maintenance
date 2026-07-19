from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, QARecord, User  # noqa: E402
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest  # noqa: E402
from app.schemas.retrieval_scope import HUAWEI_SUN2000_COMPETITION_SCOPE_ID  # noqa: E402
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService  # noqa: E402
from app.services.retrieval_scope_service import RetrievalScopeService  # noqa: E402


DATASET_PATH = BACKEND_ROOT / "tests" / "fixtures" / "task27a_huawei_sun2000_engineering_candidate_v1.json"
DEFAULT_OUTPUT = PROJECT_ROOT / ".runtime" / "task27a" / "keyword_evaluation.json"
EXPECTED_COMPOSITION = {
    "manufacturer_model": 5,
    "alarm_code": 5,
    "insulation": 4,
    "communication": 4,
    "temperature_heat": 3,
    "grid_connection": 3,
    "dc_input_mppt": 2,
    "safety_high_risk": 2,
    "no_data_out_of_scope": 2,
}
REQUIRED_CASE_FIELDS = {
    "case_id",
    "query",
    "expected_manufacturer",
    "expected_product_family",
    "expected_model",
    "expected_alarm_code",
    "expected_fault_type",
    "expected_document_ids",
    "expected_chunk_ids",
    "required_answer_points",
    "prohibited_answer_points",
    "safety_required",
    "should_abstain",
    "review_status",
    "expert_reviewed",
    "reviewer_note",
}
SUPPORT_MESSAGE = "当前版本正式支持华为 SUN2000 系列光伏逆变器检修知识。"


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 3)


def _normalize(value: Any) -> str:
    return str(value or "").strip().casefold()


def _contains_point(text_value: str, point: str) -> bool:
    compact_text = "".join(text_value.casefold().split())
    compact_point = "".join(str(point).casefold().split())
    return bool(compact_point and compact_point in compact_text)


def _semantic_normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    normalized = normalized.replace("分钟", "min")
    normalized = normalized.replace("清除", "清理").replace("移除", "清理")
    normalized = normalized.replace("间距", "距离")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)


def _normalized_contains_point(text_value: str, point: str) -> bool:
    normalized_text = _semantic_normalize(text_value)
    normalized_point = _semantic_normalize(point)
    if not normalized_point:
        return False
    if normalized_point in normalized_text:
        return True

    action_groups = {
        "清理": ("清理", "清除", "移除"),
        "检查": ("检查", "核对", "确认"),
        "测量": ("测量", "检测", "量取"),
        "等待": ("等待", "静置"),
        "安装": ("安装", "装配"),
    }
    canonical_point = unicodedata.normalize("NFKC", str(point or "")).casefold()
    for canonical_action, variants in action_groups.items():
        if canonical_action not in canonical_point and not any(value in canonical_point for value in variants):
            continue
        action_positions = [normalized_text.find(_semantic_normalize(value)) for value in variants]
        action_positions = [position for position in action_positions if position >= 0]
        if not action_positions:
            return False
        object_text = canonical_point
        for value in variants:
            object_text = object_text.replace(value, "")
        object_text = re.sub(r"[的地得上中内外时后前进行应需]+", "", object_text)
        normalized_object = _semantic_normalize(object_text)
        if not normalized_object:
            return False
        object_position = normalized_text.find(normalized_object)
        if object_position < 0:
            return False
        return min(abs(action_position - object_position) for action_position in action_positions) <= 48
    return False


def _dcg(relevance: list[int]) -> float:
    return sum(value / math.log2(index + 2) for index, value in enumerate(relevance))


def _load_dataset(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    cases = payload.get("cases") or []
    if payload.get("status") != "ENGINEERING_CANDIDATE":
        raise ValueError("Task 27A dataset must remain ENGINEERING_CANDIDATE")
    dataset_id = str(payload.get("dataset_id") or "")
    is_v2 = dataset_id == "task27a_huawei_sun2000_engineering_candidate_v2"
    if payload.get("expert_reviewed") is not False:
        raise ValueError("Task 27A dataset must not claim full-dataset expert review")
    if is_v2 and (
        payload.get("version") != "2.0.0"
        or payload.get("parent_dataset_id") != "task27a_huawei_sun2000_engineering_candidate_v1"
        or not payload.get("parent_dataset_sha256")
        or not payload.get("expert_review_csv_sha256")
    ):
        raise ValueError("Task 27A v2 lineage metadata is incomplete")
    if len(cases) != 30:
        raise ValueError(f"Task 27A dataset must contain 30 cases, got {len(cases)}")
    composition = Counter(item.get("category") for item in cases)
    if dict(composition) != EXPECTED_COMPOSITION:
        raise ValueError(f"unexpected Task 27A composition: {dict(composition)}")
    case_ids = [str(item.get("case_id")) for item in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Task 27A dataset contains duplicate case_id values")
    for item in cases:
        missing = REQUIRED_CASE_FIELDS - set(item)
        if missing:
            raise ValueError(f"{item.get('case_id')} missing fields: {sorted(missing)}")
        accepted_sets = list(item.get("accepted_evidence_sets") or [])
        if accepted_sets:
            if not is_v2:
                raise ValueError(f"{item.get('case_id')} adds accepted evidence outside v2")
            if item.get("review_status") != "expert_evidence_approved" or item.get("expert_reviewed") is not True:
                raise ValueError(f"{item.get('case_id')} has an invalid expert evidence claim")
            required_points = set(item["required_answer_points"])
            for evidence_set in accepted_sets:
                chunk_ids = list(evidence_set.get("chunk_ids") or [])
                covered = set(evidence_set.get("required_answer_points_covered") or [])
                if not chunk_ids or covered != required_points:
                    raise ValueError(f"{item.get('case_id')} has an incomplete accepted evidence set")
        elif item.get("review_status") != "engineering_candidate" or item.get("expert_reviewed") is not False:
            raise ValueError(f"{item.get('case_id')} has an invalid review claim")
    return payload, hashlib.sha256(raw).hexdigest()


def _case_evidence_sets(case: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_sets = []
    historic_chunk_ids = list(dict.fromkeys(str(value) for value in case["expected_chunk_ids"]))
    if historic_chunk_ids:
        evidence_sets.append({
            "evidence_set_id": f"{case['case_id']}-HISTORIC",
            "chunk_ids": historic_chunk_ids,
            "document_ids": list(dict.fromkeys(str(value) for value in case["expected_document_ids"])),
            "source": "historic",
        })
    for item in case.get("accepted_evidence_sets") or []:
        evidence_sets.append({
            "evidence_set_id": str(item["evidence_set_id"]),
            "chunk_ids": list(dict.fromkeys(str(value) for value in item["chunk_ids"])),
            "document_ids": list(dict.fromkeys(str(value) for value in item["document_ids"])),
            "source": "expert_accepted",
            "preferred": bool(item.get("preferred")),
        })
    return evidence_sets


def _completed_evidence_sets(
    evidence_sets: list[dict[str, Any]],
    ranked_chunk_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    surfaced = set(ranked_chunk_ids[:limit])
    return [
        item
        for item in evidence_sets
        if item["chunk_ids"] and set(item["chunk_ids"]).issubset(surfaced)
    ]


def _evidence_set_completion_rank(
    evidence_sets: list[dict[str, Any]],
    ranked_chunk_ids: list[str],
) -> tuple[int | None, dict[str, Any] | None]:
    positions = {chunk_id: index for index, chunk_id in enumerate(ranked_chunk_ids, start=1)}
    completed = []
    for item in evidence_sets:
        if item["chunk_ids"] and all(chunk_id in positions for chunk_id in item["chunk_ids"]):
            completed.append((max(positions[chunk_id] for chunk_id in item["chunk_ids"]), item))
    return min(completed, key=lambda value: value[0]) if completed else (None, None)


def _database_counts(db) -> dict[str, int]:
    return {
        "knowledge_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
        "knowledge_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
        "qa_records": int(db.scalar(select(func.count()).select_from(QARecord)) or 0),
    }


def _gate(metric: float | None, threshold: float, operator: str = ">=") -> dict[str, Any]:
    if metric is None:
        return {"threshold": threshold, "operator": operator, "value": None, "passed": False}
    passed = metric >= threshold if operator == ">=" else metric == threshold
    return {"threshold": threshold, "operator": operator, "value": metric, "passed": passed}


def _signal_match(actual: Any, expected: str) -> bool:
    return _normalize(actual) == _normalize(expected)


def run_evaluation(dataset_path: Path) -> dict[str, Any]:
    dataset, dataset_sha256 = _load_dataset(dataset_path)
    cases: list[dict[str, Any]] = dataset["cases"]

    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.is_active.is_(True)).order_by(User.created_at, User.id))
        if actor is None:
            raise RuntimeError("Task 27A evaluation requires one existing active user")
        service = QueryAwareRetrievalService(db, current_user=actor)
        db.execute(text("SET TRANSACTION READ ONLY"))
        counts_before = _database_counts(db)
        scope = RetrievalScopeService(db).resolve(
            HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
            pilot_required=True,
        )
        scope_document_ids = {str(value) for value in scope.allowed_document_ids}
        documents = {
            str(item.id): item
            for item in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(scope.allowed_document_ids)))
        }
        chunks = {
            str(item.id): item
            for item in db.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.document_id.in_(scope.allowed_document_ids),
                    KnowledgeChunk.status == scope.required_chunk_status,
                )
            )
        }

        labelled_documents = {value for case in cases for value in case["expected_document_ids"]}
        labelled_chunks = {value for case in cases for value in case["expected_chunk_ids"]}
        missing_labelled_documents = sorted(labelled_documents - set(documents))
        missing_labelled_chunks = sorted(labelled_chunks - set(chunks))
        if missing_labelled_documents or missing_labelled_chunks:
            raise RuntimeError(
                "frozen dataset references evidence outside the current formal scope: "
                f"documents={missing_labelled_documents}, chunks={missing_labelled_chunks}"
            )

        results: list[dict[str, Any]] = []
        latency_ms: list[float] = []
        recalls = {1: [], 3: [], 5: []}
        reciprocal_ranks: list[float] = []
        ndcg_values: list[float] = []
        signal_totals = Counter()
        signal_correct = Counter()
        citation_count = 0
        valid_citation_count = 0
        citation_support_total = 0
        citation_support_correct = 0
        answer_point_total = 0
        answer_point_covered = 0
        normalized_answer_point_covered = 0
        abstention_correct = 0
        safety_total = 0
        safety_correct = 0
        outside_scope_citations = 0
        pending_or_archived_citations = 0
        cross_manufacturer_citations = 0

        for case in cases:
            started = time.perf_counter()
            response = service.search(QueryAwareSearchRequest(
                query=case["query"],
                request_id=f"task27a-eval-{case['case_id'].lower()}",
                retrieval_mode="fast",
                top_k=5,
                enable_llm=False,
                allow_real_api=False,
                persist_result=False,
            ))
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            latency_ms.append(elapsed)
            references = list(response.references[:5])
            ranked_chunk_ids = [str(item.get("chunk_id")) for item in references if item.get("chunk_id")]
            configured_evidence_sets = _case_evidence_sets(case)
            evidence_sets = [
                item
                for item in configured_evidence_sets
                if set(item["chunk_ids"]).issubset(chunks)
                and set(item["document_ids"]).issubset(documents)
            ]
            if not any(item["source"] == "historic" for item in evidence_sets) and case["expected_chunk_ids"]:
                raise RuntimeError(f"{case['case_id']} historic evidence is unavailable in the current corpus")
            labelled_chunk_ids = {
                value for evidence_set in evidence_sets for value in evidence_set["chunk_ids"]
            }
            raw_chunk_ids = {item.chunk_id for item in response.raw_results}
            failures: list[dict[str, str]] = []

            matched_set: dict[str, Any] | None = None
            if evidence_sets:
                for k in (1, 3, 5):
                    recalls[k].append(float(bool(_completed_evidence_sets(evidence_sets, ranked_chunk_ids, k))))
                first_rank, matched_set = _evidence_set_completion_rank(evidence_sets, ranked_chunk_ids)
                reciprocal_ranks.append(1 / first_rank if first_rank else 0.0)
                ndcg_values.append(1 / math.log2(first_rank + 1) if first_rank else 0.0)
                if first_rank is None:
                    category = "RANKING" if labelled_chunk_ids.intersection(raw_chunk_ids) else "RETRIEVAL"
                    failures.append({"category": category, "reason": "no complete labelled evidence set was surfaced in top 5"})

            signals = dict(response.query_signals or {})
            expected_manufacturer = case["expected_manufacturer"]
            if expected_manufacturer == "huawei":
                signal_totals["manufacturer"] += 1
                if _signal_match(signals.get("manufacturer"), expected_manufacturer):
                    signal_correct["manufacturer"] += 1
                else:
                    failures.append({"category": "QUERY_SIGNAL", "reason": "manufacturer mismatch"})
            expected_product = case["expected_product_family"]
            if expected_product in {"SUN2000", "FusionSolar"}:
                signal_totals["product_family"] += 1
                if _signal_match(signals.get("product_family"), expected_product):
                    signal_correct["product_family"] += 1
                else:
                    failures.append({"category": "QUERY_SIGNAL", "reason": "product family mismatch"})
            expected_model = case["expected_model"]
            if expected_model.upper().startswith("SUN2000"):
                signal_totals["model"] += 1
                if _signal_match(signals.get("model"), expected_model):
                    signal_correct["model"] += 1
                else:
                    failures.append({"category": "MODEL", "reason": "exact model mismatch"})
            expected_alarm = case["expected_alarm_code"]
            if expected_alarm:
                signal_totals["alarm_code"] += 1
                if _signal_match(signals.get("alarm_code"), expected_alarm):
                    signal_correct["alarm_code"] += 1
                else:
                    failures.append({"category": "ALARM_CODE", "reason": "alarm code mismatch"})

            case_citations_valid = True
            for reference in references:
                citation_count += 1
                chunk_id = str(reference.get("chunk_id") or "")
                document_id = str(reference.get("document_id") or "")
                chunk = chunks.get(chunk_id)
                document = documents.get(document_id)
                valid = bool(
                    chunk
                    and document
                    and str(chunk.document_id) == document_id
                    and document_id in scope_document_ids
                    and chunk.status == scope.required_chunk_status
                )
                valid_citation_count += int(valid)
                case_citations_valid = case_citations_valid and valid
                if document_id not in scope_document_ids:
                    outside_scope_citations += 1
                if document and (
                    document.status != "active"
                    or document.parse_status != "parsed"
                    or document.review_status != "approved"
                ):
                    pending_or_archived_citations += 1
                if document and _normalize(document.manufacturer) not in {"huawei", "华为"}:
                    cross_manufacturer_citations += 1
            if not case_citations_valid:
                failures.append({"category": "CITATION", "reason": "one or more references failed scope validation"})

            if evidence_sets:
                citation_support_total += 1
                citation_supported = bool(_completed_evidence_sets(evidence_sets, ranked_chunk_ids, 5))
                citation_support_correct += int(citation_supported)
                if not citation_supported:
                    failures.append({"category": "CITATION", "reason": "references do not include a complete labelled evidence set"})

            combined_answer = "\n".join([
                response.answer,
                response.message,
                *response.suggested_steps,
                *response.safety_notes,
            ])
            required_points = list(case["required_answer_points"])
            covered_points = [point for point in required_points if _contains_point(combined_answer, point)]
            normalized_covered_points = [
                point for point in required_points if _normalized_contains_point(combined_answer, point)
            ]
            answer_point_total += len(required_points)
            answer_point_covered += len(covered_points)
            normalized_answer_point_covered += len(normalized_covered_points)
            case_answer_coverage = _ratio(len(covered_points), len(required_points)) or 0.0
            normalized_case_answer_coverage = (
                _ratio(len(normalized_covered_points), len(required_points)) or 0.0
            )
            if case_answer_coverage < 0.85:
                failures.append({"category": "ANSWER", "reason": "required answer-point coverage below 0.85"})
            prohibited_found = [
                point for point in case["prohibited_answer_points"] if _contains_point(combined_answer, point)
            ]
            if prohibited_found:
                failures.append({"category": "ANSWER", "reason": "prohibited answer point present"})

            abstention_matches = bool(response.abstained) == bool(case["should_abstain"])
            abstention_correct += int(abstention_matches)
            if not abstention_matches:
                failures.append({"category": "ABSTENTION", "reason": "abstention decision mismatch"})
            if case["should_abstain"] and (
                references or response.retrieved_chunks or response.message != SUPPORT_MESSAGE
            ):
                failures.append({"category": "SCOPE", "reason": "unsupported query leaked evidence or support message changed"})

            case_safety_ok: bool | None = None
            if case["safety_required"]:
                safety_total += 1
                safety_text = " ".join(response.safety_notes)
                case_safety_ok = bool(response.safety_notes) and any(
                    term in safety_text for term in ("安全", "下电", "断电", "带电", "电击", "触电", "防护", "专业")
                )
                safety_correct += int(case_safety_ok)
                if not case_safety_ok:
                    failures.append({"category": "SAFETY", "reason": "electrical safety guidance missing"})

            results.append({
                "case_id": case["case_id"],
                "category": case["category"],
                "query": case["query"],
                "expected": {
                    "manufacturer": case["expected_manufacturer"],
                    "product_family": case["expected_product_family"],
                    "model": case["expected_model"],
                    "alarm_code": case["expected_alarm_code"],
                    "fault_type": case["expected_fault_type"],
                    "document_ids": case["expected_document_ids"],
                    "chunk_ids": case["expected_chunk_ids"],
                    "evidence_sets": evidence_sets,
                    "configured_evidence_sets": configured_evidence_sets,
                    "matched_evidence_set": matched_set,
                    "evidence_set_completion_rank": first_rank if evidence_sets else None,
                    "should_abstain": case["should_abstain"],
                },
                "actual": {
                    "signals": signals,
                    "document_ids": list(dict.fromkeys(str(item.get("document_id")) for item in references)),
                    "chunk_ids": ranked_chunk_ids,
                    "answer": response.answer,
                    "message": response.message,
                    "references": references,
                    "abstained": response.abstained,
                    "confidence": response.confidence,
                    "persistence_status": response.persistence_status,
                    "actual_channels": response.actual_channels,
                },
                "required_answer_points": required_points,
                "strict_covered_answer_points": covered_points,
                "normalized_covered_answer_points": normalized_covered_points,
                "strict_answer_point_coverage": case_answer_coverage,
                "normalized_answer_point_coverage": normalized_case_answer_coverage,
                "covered_answer_points": covered_points,
                "answer_point_coverage": case_answer_coverage,
                "safety_ok": case_safety_ok,
                "latency_ms": elapsed,
                "failures": failures,
                "passed": not failures,
                "fix": "pending engineering review" if failures else "none",
                "retest": "not rerun after baseline" if failures else "baseline passed",
            })

        counts_after = _database_counts(db)
        db.rollback()

    metrics = {
        "recall_at_1": round(statistics.fmean(recalls[1]), 6) if recalls[1] else None,
        "recall_at_3": round(statistics.fmean(recalls[3]), 6) if recalls[3] else None,
        "recall_at_5": round(statistics.fmean(recalls[5]), 6) if recalls[5] else None,
        "mrr": round(statistics.fmean(reciprocal_ranks), 6) if reciprocal_ranks else None,
        "ndcg_at_5": round(statistics.fmean(ndcg_values), 6) if ndcg_values else None,
        "manufacturer_accuracy": _ratio(signal_correct["manufacturer"], signal_totals["manufacturer"]),
        "product_family_accuracy": _ratio(signal_correct["product_family"], signal_totals["product_family"]),
        "model_accuracy": _ratio(signal_correct["model"], signal_totals["model"]),
        "alarm_code_accuracy": _ratio(signal_correct["alarm_code"], signal_totals["alarm_code"]),
        "citation_validity": _ratio(valid_citation_count, citation_count),
        "citation_support": _ratio(citation_support_correct, citation_support_total),
        "required_answer_point_coverage": _ratio(answer_point_covered, answer_point_total),
        "fabricated_citation_rate": _ratio(citation_count - valid_citation_count, citation_count),
        "cross_manufacturer_contamination": _ratio(cross_manufacturer_citations, citation_count),
        "abstention_accuracy": _ratio(abstention_correct, len(cases)),
        "safety_coverage": _ratio(safety_correct, safety_total),
        "out_of_scope_evidence_rate": _ratio(outside_scope_citations, citation_count),
        "pending_archived_evidence_rate": _ratio(pending_or_archived_citations, citation_count),
        "p50_latency_ms": _percentile(latency_ms, 0.50),
        "p95_latency_ms": _percentile(latency_ms, 0.95),
    }
    strict_metrics = dict(metrics)
    normalized_metrics = {
        **metrics,
        "required_answer_point_coverage": _ratio(
            normalized_answer_point_covered,
            answer_point_total,
        ),
    }
    gates = {
        "recall_at_1": _gate(metrics["recall_at_1"], 0.75),
        "recall_at_3": _gate(metrics["recall_at_3"], 0.90),
        "recall_at_5": _gate(metrics["recall_at_5"], 0.95),
        "mrr": _gate(metrics["mrr"], 0.85),
        "ndcg_at_5": _gate(metrics["ndcg_at_5"], 0.85),
        "manufacturer_accuracy": _gate(metrics["manufacturer_accuracy"], 1.0, "=="),
        "product_family_accuracy": _gate(metrics["product_family_accuracy"], 1.0, "=="),
        "model_accuracy": _gate(metrics["model_accuracy"], 0.90),
        "alarm_code_accuracy": _gate(metrics["alarm_code_accuracy"], 0.90),
        "out_of_scope_evidence_rate": _gate(metrics["out_of_scope_evidence_rate"], 0.0, "=="),
        "pending_archived_evidence_rate": _gate(metrics["pending_archived_evidence_rate"], 0.0, "=="),
        "citation_validity": _gate(metrics["citation_validity"], 1.0, "=="),
        "citation_support": _gate(metrics["citation_support"], 0.90),
        "required_answer_point_coverage": _gate(metrics["required_answer_point_coverage"], 0.85),
        "fabricated_citation_rate": _gate(metrics["fabricated_citation_rate"], 0.0, "=="),
        "cross_manufacturer_contamination": _gate(metrics["cross_manufacturer_contamination"], 0.0, "=="),
        "safety_coverage": _gate(metrics["safety_coverage"], 1.0, "=="),
        "abstention_accuracy": _gate(metrics["abstention_accuracy"], 0.90),
    }
    engineering_gate_passed = all(item["passed"] for item in gates.values())
    failure_categories = Counter(
        failure["category"]
        for result in results
        for failure in result["failures"]
    )
    failed_cases = [item for item in results if not item["passed"]]
    production_unchanged = counts_before == counts_after
    status = "READY_WITH_FIXES" if engineering_gate_passed and production_unchanged else "NOT_READY"
    return {
        "scope": "Huawei SUN2000",
        "scope_id": HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
        "status": status,
        "delivery_ready": False,
        "evaluation_mode": "keyword_only_read_only",
        "database": {
            "name": engine.url.database,
            "read_only_transaction": True,
            "persist_result": False,
            "counts_before": counts_before,
            "counts_after": counts_after,
            "production_database_unchanged": production_unchanged,
        },
        "evaluation_dataset": {
            "dataset_id": dataset["dataset_id"],
            "version": dataset["version"],
            "sha256": dataset_sha256,
            "case_count": len(cases),
            "composition": dataset["composition"],
            "expert_reviewed": bool(dataset.get("expert_reviewed")),
            "status": dataset["status"],
            "expert_quality_gate": dataset.get("expert_quality_gate"),
        },
        "keyword_metrics": metrics,
        "strict_metrics": strict_metrics,
        "normalized_metrics": normalized_metrics,
        "engineering_gate_metric_basis": "strict",
        "metric_denominators": {
            "retrieval_cases": len(reciprocal_ranks),
            "manufacturer_cases": signal_totals["manufacturer"],
            "product_family_cases": signal_totals["product_family"],
            "exact_model_cases": signal_totals["model"],
            "alarm_code_cases": signal_totals["alarm_code"],
            "citation_count": citation_count,
            "citation_support_cases": citation_support_total,
            "required_answer_points": answer_point_total,
            "safety_cases": safety_total,
            "abstention_cases": len(cases),
        },
        "quality_gates": gates,
        "normalized_quality_gates": {
            **gates,
            "required_answer_point_coverage": _gate(
                normalized_metrics["required_answer_point_coverage"],
                0.85,
            ),
        },
        "engineering_gate_passed": engineering_gate_passed,
        "hybrid_metrics": {
            "status": "BLOCKED",
            "executed": False,
            "reason": "No authorized embedding/DashVector provider was used for Task 27A-R2.",
            "recall_at_5": None,
            "p95_latency_ms": None,
        },
        "failure_summary": {
            "failed_case_count": len(failed_cases),
            "failure_event_count": sum(failure_categories.values()),
            "categories": dict(sorted(failure_categories.items())),
        },
        "cases": results,
        "remaining_blockers": [
            "Thirty-case dataset has not been reviewed by a human Huawei inverter-maintenance expert.",
            "Isolated PostgreSQL persistence integration is blocked because the current role cannot create a test database.",
            "Hybrid evaluation is blocked because no authorized provider was used.",
            *([] if engineering_gate_passed else ["One or more keyword engineering quality gates failed."]),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the read-only Task 27A Huawei SUN2000 keyword evaluation")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_evaluation(args.dataset.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "dataset": result["evaluation_dataset"],
        "keyword_metrics": result["keyword_metrics"],
        "engineering_gate_passed": result["engineering_gate_passed"],
        "failure_summary": result["failure_summary"],
        "hybrid": result["hybrid_metrics"],
        "database": result["database"],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
