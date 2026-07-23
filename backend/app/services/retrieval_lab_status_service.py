from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    MaintenanceSemanticAnchor,
    RetrievalDatasetFreeze,
    RetrievalEvaluationCase,
    RetrievalEvaluationRun,
)
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService


class RetrievalLabStatusService:
    """Read isolated retrieval research state when the lab is enabled."""

    ROOT = Path(__file__).resolve().parents[3]
    STAGE_ROOTS = {
        "r2": ROOT / ".runtime" / "task25b_r3_dev_r2",
        "r3": ROOT / ".runtime" / "task25b_r3_dev_r3",
        "r4": ROOT / ".runtime" / "task25b_r3_dev_r4",
        "r5": ROOT / ".runtime" / "task25b_r3_dev_r5",
        "r5_r1": ROOT / ".runtime" / "task25b_r3_dev_r5_r1",
        "r5_r2_mm": ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm",
        "r5_r3_mm": ROOT / ".runtime" / "task25b_r3_dev_r5_r3_mm",
        "r5_r4_mm": ROOT / ".runtime" / "task25b_r3_dev_r5_r4_mm",
        "r5_r5": ROOT / ".runtime" / "task25b_r3_dev_r5_r5",
        "r5_r6": ROOT / ".runtime" / "task25b_r3_dev_r5_r6",
    }

    def __init__(self, db: Session):
        self.db = db

    def r1_status(self) -> dict:
        scope = RetrievalScopeService(self.db).resolve(
            CHINESE_ENGINEERING_PILOT_SCOPE_ID,
            pilot_required=True,
        )
        first_run = self.db.scalar(
            select(RetrievalEvaluationRun).where(
                RetrievalEvaluationRun.id
                == UUID("f1941ec2-9878-45a1-b554-8d9f2f2ec911")
            )
        )
        second_run = self.db.scalar(
            select(RetrievalEvaluationRun)
            .where(
                RetrievalEvaluationRun.name
                == "task25b_r3_dev_r1_zh_quality_gate_v2"
            )
            .order_by(RetrievalEvaluationRun.created_at.desc())
        )
        return {
            "scope": scope.public_dict(),
            "scope_validation_passed": True,
            "benchmark_dataset_status": "BENCHMARK_DATASET_READY",
            "v1_run": (
                {
                    "run_id": str(first_run.id),
                    "preserved": True,
                    "quality_gate_status": "QUALITY_GATE_FAILED",
                }
                if first_run
                else None
            ),
            "v2_run": (
                {
                    "run_id": str(second_run.id),
                    "preserved": True,
                    "quality_gate_status": "QUALITY_GATE_FAILED",
                }
                if second_run
                else None
            ),
            "canary_status": "CANARY_PASSED",
            "full_quality_gate_status": "QUALITY_GATE_FAILED",
            "expert_verified": False,
        }

    def r2_status(self) -> dict:
        previous_run = self.db.get(
            RetrievalEvaluationRun,
            UUID("3e40e25f-f1f1-4146-9e1e-629d2ce76045"),
        )
        cases = list(
            self.db.scalars(
                select(RetrievalEvaluationCase).where(
                    RetrievalEvaluationCase.metadata_json[
                        "dataset_version"
                    ].as_string()
                    == "task25b_r3_dev_r2_zh_v3"
                )
            )
        )
        freeze = self.db.scalar(
            select(RetrievalDatasetFreeze).where(
                RetrievalDatasetFreeze.dataset_version
                == "task25b_r3_dev_r2_zh_v3_test_v3"
            )
        )
        canary = self._artifact("r2", "canary_result.json")
        contract = self._artifact("r2", "metric_contract_audit.json")
        manifest = self._artifact("r2", "dataset_v3_manifest.json")
        distinctness = self._artifact("r2", "mode_distinctness_v2.json")
        return {
            "v2_run": (
                {
                    "run_id": str(previous_run.id),
                    "preserved": True,
                    "quality_gate_status": "QUALITY_GATE_FAILED",
                }
                if previous_run
                else None
            ),
            "v3_dataset": {
                "dataset_version": "task25b_r3_dev_r2_zh_v3",
                "cases": len(cases),
                "frozen": bool(freeze),
                "freeze_status": (
                    freeze.freeze_status if freeze else "NOT_FROZEN"
                ),
                "coverage": manifest.get("test_v3_coverage") or {},
            },
            "metric_contract": {
                key: contract.get(key)
                for key in (
                    "single_relevant_cases",
                    "multi_relevant_cases",
                    "impossible_precision_at_5_cases",
                    "quality_gate_contract_corrected",
                )
            },
            "canary": {
                key: canary.get(key)
                for key in ("status", "passed", "checks", "vector_heavy", "by_mode")
            },
            "mode_distinctness": {
                key: distinctness.get(key)
                for key in (
                    "keyword_vector_candidate_jaccard_mean",
                    "keyword_vector_rank_correlation_mean",
                    "identical_case_rate",
                    "gate",
                )
            },
            "quality_gate_status": (
                "NOT_RUN_CANARY_FAILED"
                if canary and not canary.get("passed")
                else "PENDING_TEST_V3_FREEZE"
            ),
            "expert_verified": False,
        }

    def r3_status(self) -> dict:
        snapshot = self._artifact("r3", "r2_snapshot.json")
        grounding = self._artifact("r3", "vector_heavy_grounding.json")
        embedding = self._artifact("r3", "embedding_pair_diagnostics.json")
        recall_trace = self._artifact("r3", "dashvector_recall_trace.json")
        anchor_index = self._artifact("r3", "semantic_anchor_index.json")
        reconciliation = self._artifact(
            "r3", "semantic_reconciliation.json"
        )
        canary = self._artifact("r3", "canary_result.json")
        anchor_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(MaintenanceSemanticAnchor)
                .where(
                    MaintenanceSemanticAnchor.namespace
                    == "pilot_r3_semantic",
                    MaintenanceSemanticAnchor.index_status == "active",
                )
            )
            or 0
        )
        return {
            "r2_canary": {
                "status": snapshot.get("r2_canary_status"),
                "preserved": bool(snapshot),
                "read_only": snapshot.get("read_only"),
            },
            "grounding": {
                key: grounding.get(key)
                for key in ("cases_reviewed", "summary", "usable_canary_cases")
            },
            "embedding": {
                key: embedding.get(key)
                for key in (
                    "pairs",
                    "primary_diagnosis",
                    "averages",
                    "semantic_minus_raw",
                )
            },
            "raw_dashvector": {
                key: recall_trace.get(key)
                for key in (
                    "cases",
                    "raw_top50_hit",
                    "post_filter_hit",
                    "mapping_failures",
                    "filter_drops",
                    "content_mismatches",
                    "summary",
                )
            },
            "semantic_index": {
                "collection": anchor_index.get("collection"),
                "raw_partition": "pilot_r2",
                "semantic_partition": "pilot_r3_semantic",
                "anchor_vectors": anchor_count,
                "anchor_types": anchor_index.get("anchor_types") or {},
                "reconciliation": {
                    key: reconciliation.get(key)
                    for key in (
                        "missing_anchor",
                        "orphan_anchor",
                        "duplicate_anchor_id",
                        "representation_hash_mismatch",
                        "language_leakage",
                        "status_leakage",
                    )
                },
            },
            "canary": {
                "status": canary.get("status"),
                "checks": canary.get("checks") or {},
                "vector_heavy": canary.get("vector_heavy") or {},
                "by_mode": canary.get("by_mode") or {},
                "formal_test_v3_1_used": bool(
                    canary.get("formal_test_v3_1_used")
                ),
            },
            "test_v3_1": {
                "dataset": None,
                "frozen": False,
                "official_run_count": 0,
                "quality_gate": "NOT_RUN_CANARY_FAILED",
            },
            "default_partition_changed": False,
            "pilot_r2_changed": False,
            "full_reindex": False,
            "expert_verified": False,
        }

    def r4_status(self) -> dict:
        manifest = self._artifact("r4", "semantic_unit_manifest.json")
        quality = self._artifact("r4", "semantic_unit_quality.json")
        grounding = self._artifact("r4", "grounding_audit.json")
        index = self._artifact("r4", "semantic_unit_index.json")
        reconciliation = self._artifact(
            "r4", "semantic_unit_reconciliation.json"
        )
        margin = self._artifact("r4", "embedding_margin.json")
        canary = self._artifact("r4", "canary_iteration_2.json") or self._artifact(
            "r4", "canary_iteration_1.json"
        )
        formal = self._artifact("r4", "quality_gate_v4.json")
        anchor_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(MaintenanceSemanticAnchor)
                .where(
                    MaintenanceSemanticAnchor.namespace
                    == "pilot_r4_grounded",
                    MaintenanceSemanticAnchor.index_status == "active",
                )
            )
            or 0
        )
        return {
            "history": {
                "r2_canary": "CANARY_FAILED",
                "r3_canary": "CANARY_FAILED",
                "preserved": True,
                "read_only": True,
            },
            "semantic_units": {
                "documents": manifest.get("documents"),
                "eligible_sections": manifest.get("eligible_sections"),
                "units": manifest.get("semantic_units"),
                "unit_types": manifest.get("unit_types") or {},
                "quality_status": (
                    "PASSED" if quality.get("passed") else "FAILED"
                ),
            },
            "grounding": {
                "dataset": grounding.get("dataset"),
                "total_cases": grounding.get("total_cases"),
                "summary": grounding.get("summary") or {},
                "vector_heavy": grounding.get("vector_heavy"),
                "lexical_leakage": grounding.get("lexical_leakage"),
                "expert_verified": 0,
            },
            "semantic_index": {
                "collection": index.get("collection"),
                "raw_partition": "pilot_r2",
                "r3_partition": "pilot_r3_semantic",
                "r4_partition": "pilot_r4_grounded",
                "semantic_units": index.get("semantic_units"),
                "anchor_vectors": anchor_count,
                "anchor_types": index.get("anchor_types") or {},
                "reconciliation": {
                    key: reconciliation.get(key)
                    for key in (
                        "missing",
                        "orphan",
                        "duplicate",
                        "hash_mismatch",
                        "language_leakage",
                        "quality_leakage",
                    )
                },
            },
            "embedding_margin": {
                "status": margin.get("status"),
                "summary": margin.get("summary") or {},
            },
            "canary": {
                "status": canary.get("status") or "NOT_RUN",
                "iteration": canary.get("iteration"),
                "checks": canary.get("checks") or {},
                "vector_heavy": canary.get("vector_heavy") or {},
                "by_mode": canary.get("by_mode") or {},
            },
            "formal_v4": {
                "dataset": formal.get("dataset"),
                "frozen": bool(formal.get("frozen")),
                "run_count": int(formal.get("run_count") or 0),
                "result": formal.get("status")
                or "NOT_RUN_CANARY_NOT_PASSED",
            },
            "boundaries": {
                "viewer_read_only": True,
                "default_partition_changed": False,
                "original_vectors_reindexed": False,
                "full_reindex": False,
                "expert_verified": False,
            },
        }

    def r5_status(self) -> dict:
        stage_files = {
            "r5": (
                "semantic_unit_v2_manifest.json",
                "query_understanding_metrics.json",
                "canary_result.json",
                "formal_quality_gate.json",
            ),
            "r5_r1": (
                "structured_model_probe.json",
                "rerank_probe.json",
                "canary_result.json",
            ),
            "r5_r2_mm": (
                "provider_ab_result.json",
                "canary_result.json",
                "formal_quality_gate.json",
            ),
            "r5_r3_mm": (
                "contract_gate.json",
                "canary_result.json",
                "vector_reconciliation.json",
            ),
            "r5_r4_mm": (
                "label_integrity.json",
                "canary_result.json",
                "formal_quality_gate.json",
            ),
            "r5_r5": ("canary_iteration_2.json",),
            "r5_r6": (
                "config_check.json",
                "qwen_rerank_probe.json",
                "canary_iteration_2.json",
                "formal_quality_gate.json",
            ),
        }
        stages = {
            stage: {
                name: self._artifact(stage, name)
                for name in names
            }
            for stage, names in stage_files.items()
        }
        artifact_count = sum(
            bool(value)
            for stage in stages.values()
            for value in stage.values()
        )
        anchor_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(MaintenanceSemanticAnchor)
                .where(
                    MaintenanceSemanticAnchor.namespace
                    == "pilot_r5_query_aware",
                    MaintenanceSemanticAnchor.index_status == "active",
                )
            )
            or 0
        )
        return {
            "lab_enabled": True,
            "artifact_count": artifact_count,
            "anchor_vectors": anchor_count,
            "stages": stages,
            "boundaries": {
                "read_only_summary": True,
                "default_partition_changed": False,
                "full_reindex": False,
                "expert_verified": False,
            },
        }

    @classmethod
    def _artifact(cls, stage: str, name: str) -> dict:
        path = cls.STAGE_ROOTS[stage] / name
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}
