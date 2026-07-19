from __future__ import annotations

import math
import statistics
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun, User
from app.repositories.retrieval_evaluation_repository import RetrievalEvaluationRepository
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_evaluation import RetrievalEvaluationCaseCreate, RetrievalEvaluationRequest
from app.services.feature_reranker import FeatureFusionReranker
from app.services.multimodal_retrieval_service import MultimodalRetrievalService
from app.services.retrieval_service import RetrievalService
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine


class RetrievalEvaluationServiceError(ValueError):
    pass


class RetrievalEvaluationService:
    TARGETS = {"recall_at_5": 0.85, "recall_at_10": 0.95, "mrr": 0.80, "ndcg_at_10": 0.85, "citation_valid": 0.98}

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repository = RetrievalEvaluationRepository(db)

    def create_case(self, payload: RetrievalEvaluationCaseCreate, current_user: User):
        if not (payload.expected_document_ids or payload.expected_chunk_ids or payload.expected_media_ids) and payload.category != "no_answer":
            raise RetrievalEvaluationServiceError("non-no_answer cases require expected evidence IDs")
        item = RetrievalEvaluationCase(
            **payload.model_dump(mode="json"),
            created_by=current_user.id,
            reviewed_by=current_user.id if payload.review_status in {"engineering_verified", "expert_verified"} else None,
        )
        self.repository.create_case(item)
        self.db.commit()
        self.db.refresh(item)
        return self._case_dict(item)

    def list_cases(self, *, split: str | None, page: int, page_size: int) -> dict:
        items, total = self.repository.list_cases(split=split, page=page, page_size=page_size)
        return {"items": [self._case_dict(item) for item in items], "total": total, "page": page, "page_size": page_size}

    def list_runs(self, *, page: int, page_size: int) -> dict:
        items, total = self.repository.list_runs(page=page, page_size=page_size)
        return {"items": [self._run_dict(item) for item in items], "total": total, "page": page, "page_size": page_size}

    def get_run(self, run_id) -> dict | None:
        run, results = self.repository.get_run(run_id)
        if not run:
            return None
        return {**self._run_dict(run), "results": [self._result_dict(item) for item in results]}

    def evaluate(self, payload: RetrievalEvaluationRequest, current_user: User) -> dict:
        cases = self.repository.evaluation_cases(
            split=payload.dataset_split, limit=payload.max_cases, dataset_version=payload.dataset_version,
        )
        if not cases:
            raise RetrievalEvaluationServiceError("no verified evaluation cases found for selected split")
        run = self.repository.create_run(RetrievalEvaluationRun(
            name=payload.name,
            embedding_provider=self.settings.EMBEDDING_PROVIDER,
            embedding_model=self.settings.EMBEDDING_MODEL or "unavailable",
            embedding_dimension=self.settings.EMBEDDING_DIM,
            vector_backend=self.settings.VECTOR_BACKEND,
            collection_name=self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            retrieval_config_json={
                "modes": payload.modes, "split": payload.dataset_split,
                "reranker": FeatureFusionReranker().snapshot(), "test_split_tuning_allowed": False,
            },
            dataset_version=payload.dataset_version,
            run_status="running",
            started_at=datetime.now(timezone.utc),
            created_by=current_user.id,
        ))
        self.db.commit()
        mode_metrics: dict[str, list[dict]] = {mode: [] for mode in payload.modes}
        errors = 0
        for case in cases:
            for mode in payload.modes:
                started = time.perf_counter()
                try:
                    ranked_docs, ranked_chunks, ranked_media, scores, fallback, citation_valid = self._execute_case(case, mode, current_user)
                    metrics = self.compute_metrics(
                        ranked_chunks or ranked_docs or ranked_media,
                        case.expected_chunk_ids or case.expected_document_ids or case.expected_media_ids,
                    )
                    excluded = set(case.excluded_document_ids or [])
                    leakage = any(str(item) in {str(value) for value in excluded} for item in ranked_docs)
                    metrics.update({"leakage": float(leakage), "citation_valid": float(citation_valid)})
                    metrics["fallback"] = float(fallback)
                    top1_expected = bool((ranked_chunks or ranked_docs or ranked_media) and str((ranked_chunks or ranked_docs or ranked_media)[0]) in {str(item) for item in (case.expected_chunk_ids or case.expected_document_ids or case.expected_media_ids)})
                    metrics["exact_model_accuracy"] = float(top1_expected) if case.category == "device_model_query" else None
                    metrics["exact_fault_code_accuracy"] = float(top1_expected) if case.category == "fault_code_query" else None
                    passed = not leakage and (case.category == "no_answer" or metrics["recall_at_10"] > 0)
                    error_summary = None
                except Exception as exc:
                    ranked_docs = ranked_chunks = ranked_media = []
                    scores = {}
                    fallback = False
                    metrics = {**self.compute_metrics([], []), "leakage": 0.0, "citation_valid": 0.0, "fallback": 0.0,
                               "exact_model_accuracy": 0.0 if case.category == "device_model_query" else None,
                               "exact_fault_code_accuracy": 0.0 if case.category == "fault_code_query" else None}
                    passed = False
                    error_summary = type(exc).__name__
                    errors += 1
                latency = (time.perf_counter() - started) * 1000
                metrics["latency_ms"] = latency
                mode_metrics[mode].append(metrics)
                self.repository.add_result(RetrievalEvaluationResult(
                    run_id=run.id, case_id=case.id, retrieval_mode=mode,
                    ranked_document_ids=ranked_docs, ranked_chunk_ids=ranked_chunks, ranked_media_ids=ranked_media,
                    score_breakdown_json=scores, recall_at_5=metrics["recall_at_5"], recall_at_10=metrics["recall_at_10"],
                    reciprocal_rank=metrics["mrr"], ndcg_at_10=metrics["ndcg_at_10"], precision_at_5=metrics["precision_at_5"],
                    latency_ms=latency, fallback_used=fallback, passed=passed, error_summary=error_summary,
                ))
        aggregate = {mode: self.aggregate_metrics(values) for mode, values in mode_metrics.items()}
        hybrid = aggregate.get("hybrid", {}).get("ndcg_at_10")
        rerank = aggregate.get("hybrid_rerank", {}).get("ndcg_at_10")
        rerank_rollback = hybrid is not None and rerank is not None and FeatureFusionReranker.should_rollback(hybrid, rerank)
        threshold_result = self._threshold_result(aggregate, errors, len(cases) * len(payload.modes), rerank_rollback)
        run.run_status = "succeeded" if errors == 0 else "partial_failed"
        run.completed_at = datetime.now(timezone.utc)
        run.metrics_json = {
            "by_mode": aggregate, "case_count": len(cases), "result_count": len(cases) * len(payload.modes),
            "error_count": errors, "error_rate": errors / (len(cases) * len(payload.modes)),
            "rerank_rollback_required": rerank_rollback, "threshold_result": threshold_result,
        }
        self.db.add(run)
        self.db.commit()
        return self.get_run(run.id) or {}

    def _execute_case(self, case, mode: str, user: User):
        if mode in {"multimodal_descriptor", "similar_media"}:
            if not case.query_media_id:
                raise RetrievalEvaluationServiceError("multimodal case has no query_media_id")
            response = MultimodalRetrievalService(self.db).retrieve(case.query_media_id, top_k=10)
            matches = response.similar_media if mode == "similar_media" else [*response.manual_matches, *response.case_matches]
            return [], [], [str(item.object_id) for item in matches], {str(item.object_id): item.score_breakdown.model_dump() for item in matches}, False, True
        request_mode = mode
        dataset_version = str((case.metadata_json or {}).get("dataset_version") or "")
        if dataset_version in {"task25b_r2_u3_r3_dev_zh_v1", "task25b_r3_dev_r1_zh_v2", "task25b_r3_dev_r2_zh_v3"}:
            scope = RetrievalScopeService(self.db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
            request = RetrievalQueryRequest(
                question=case.query_text, retrieval_mode=request_mode, enable_vector=request_mode != "keyword",
                top_k=10, vector_top_k=20, scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID,
                **(case.required_filters or {}),
            )
            result = ScopedRetrievalEngine(self.db, scope=scope, allow_real_api=self.settings.TASK25B_ALLOW_REAL_API).retrieve(request)
            scores = dict(result.score_breakdown)
            scores["_diagnostics"] = result.diagnostics
            return (result.ranked_document_ids, result.ranked_chunk_ids, [], scores,
                    result.fallback_used, result.citation_valid)
        response = RetrievalService(self.db).query(RetrievalQueryRequest(
            question=case.query_text, retrieval_mode=request_mode, enable_vector=request_mode != "keyword",
            top_k=10, vector_top_k=20, **(case.required_filters or {}),
        ), user)
        return (
            [str(item.document_id) for item in response.retrieved_chunks],
            [str(item.chunk_id) for item in response.retrieved_chunks], [],
            {str(item.chunk_id): {"keyword_score": item.keyword_score, "vector_raw_score": item.vector_raw_score,
                                  "vector_score": item.vector_score, "rrf_score": item.rrf_score,
                                  "rerank_score": item.rerank_score, "final_score": item.final_score}
             for item in response.retrieved_chunks},
            response.fallback_used,
            bool(response.retrieval_diagnostics.get("citation_valid")),
        )

    @staticmethod
    def compute_metrics(ranked, expected) -> dict:
        ranked = [str(item) for item in ranked]
        relevant = {str(item) for item in expected}
        if not relevant:
            return {"recall_at_1": float(not ranked), "recall_at_5": float(not ranked), "recall_at_10": float(not ranked),
                    "precision_at_5": float(not ranked), "mrr": float(not ranked), "ndcg_at_10": float(not ranked),
                    "map": float(not ranked), "first_relevant_rank": None}
        hits = [1 if item in relevant else 0 for item in ranked]
        recall = lambda k: sum(hits[:k]) / len(relevant)
        precision5 = sum(hits[:5]) / 5
        first = next((index + 1 for index, hit in enumerate(hits) if hit), None)
        dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits[:10]))
        idcg = sum(1 / math.log2(index + 2) for index in range(min(10, len(relevant)))) or 1
        precisions = [sum(hits[: index + 1]) / (index + 1) for index, hit in enumerate(hits) if hit]
        return {"recall_at_1": recall(1), "recall_at_5": recall(5), "recall_at_10": recall(10),
                "precision_at_5": precision5, "mrr": 1 / first if first else 0, "ndcg_at_10": dcg / idcg,
                "map": sum(precisions) / len(relevant) if relevant else 0,
                "first_relevant_rank": first}

    @classmethod
    def compute_staged_metrics(
        cls,
        *,
        keyword_candidates: list,
        vector_candidates: list,
        final_ranked: list,
        expected: list,
        no_answer: bool,
        predicted_abstention: bool,
        latency_breakdown: dict | None = None,
        leakage: dict | None = None,
    ) -> dict:
        expected_ids = {str(item) for item in expected}

        def candidate_recall(items, k):
            if not expected_ids:
                return 1.0
            return len({str(item) for item in items[:k]} & expected_ids) / len(expected_ids)

        union = list(dict.fromkeys([*[str(item) for item in keyword_candidates], *[str(item) for item in vector_candidates]]))
        ranking = cls.compute_metrics(final_ranked, expected)
        true_abstention = bool(no_answer)
        tp = int(true_abstention and predicted_abstention)
        fp = int(not true_abstention and predicted_abstention)
        fn = int(true_abstention and not predicted_abstention)
        tn = int(not true_abstention and not predicted_abstention)
        return {
            "candidate": {
                "keyword_candidate_recall_at_20": candidate_recall(keyword_candidates, 20),
                "keyword_candidate_recall_at_50": candidate_recall(keyword_candidates, 50),
                "vector_candidate_recall_at_20": candidate_recall(vector_candidates, 20),
                "vector_candidate_recall_at_50": candidate_recall(vector_candidates, 50),
                "union_candidate_recall_at_50": candidate_recall(union, 50),
            },
            "ranking": ranking,
            "filter": {
                "pending_leakage": float(bool((leakage or {}).get("pending"))),
                "archived_leakage": float(bool((leakage or {}).get("archived"))),
                "wrong_device_leakage": float(bool((leakage or {}).get("wrong_device"))),
                "wrong_fault_code_leakage": float(bool((leakage or {}).get("wrong_fault_code"))),
            },
            "no_answer": {
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "abstention_correct": float(true_abstention == predicted_abstention),
            },
            "latency": latency_breakdown or {},
        }

    @staticmethod
    def aggregate_metrics(values: list[dict]) -> dict:
        keys = ("recall_at_1", "recall_at_5", "recall_at_10", "precision_at_5", "mrr", "ndcg_at_10", "map", "leakage", "citation_valid", "fallback")
        latencies = sorted(item["latency_ms"] for item in values)
        percentile = lambda p: latencies[min(len(latencies) - 1, max(0, math.ceil(p * len(latencies)) - 1))] if latencies else 0
        result = {key: round(statistics.fmean(item[key] for item in values), 6) for key in keys}
        for key in ("exact_model_accuracy", "exact_fault_code_accuracy"):
            selected = [item[key] for item in values if item.get(key) is not None]
            result[key] = round(statistics.fmean(selected), 6) if selected else None
        result.update({"latency_p50_ms": round(percentile(.50), 3), "latency_p95_ms": round(percentile(.95), 3), "latency_p99_ms": round(percentile(.99), 3)})
        return result

    def _threshold_result(self, aggregate: dict, errors: int, count: int, rerank_rollback: bool) -> dict:
        preferred = aggregate.get("hybrid_rerank") or aggregate.get("hybrid") or {}
        checks = {name: preferred.get(name, 0) >= target for name, target in self.TARGETS.items()}
        checks.update({"leakage": preferred.get("leakage", 1) == 0, "p95": preferred.get("latency_p95_ms", math.inf) <= 3500,
                       "model_accuracy": preferred.get("exact_model_accuracy") == 1.0,
                       "fault_code_accuracy": preferred.get("exact_fault_code_accuracy") == 1.0,
                       "error_rate": errors == 0, "rerank_no_regression": not rerank_rollback})
        return {"passed": all(checks.values()) and count > 0, "checks": checks}

    @staticmethod
    def _case_dict(item) -> dict:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    @staticmethod
    def _run_dict(item) -> dict:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    @staticmethod
    def _result_dict(item) -> dict:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}
