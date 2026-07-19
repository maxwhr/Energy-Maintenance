from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    MultimodalDiagnosticHypothesis,
    MultimodalEvidenceConflict,
    MultimodalEvidenceItem,
    MultimodalMaintenanceCase,
    OperationLog,
)


class MultimodalQualityStatusService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.runtime = Path(__file__).resolve().parents[3] / ".runtime" / "task25c"

    def collect(self) -> dict:
        benchmark = self._artifact("multimodal_benchmark_metrics.json")
        quality = self._artifact("multimodal_quality_gate.json")
        return {
            "feature": "task25c_multimodal_maintenance",
            "status": quality.get("status") or "DEVELOPMENT_IN_PROGRESS",
            "case_model": {
                "cases": self._count(MultimodalMaintenanceCase),
                "evidence_items": self._count(MultimodalEvidenceItem),
                "regions": int(self.db.scalar(select(func.count()).select_from(MultimodalEvidenceItem).where(
                    MultimodalEvidenceItem.region_id.is_not(None)
                )) or 0),
                "conflicts": self._count(MultimodalEvidenceConflict),
                "hypotheses": self._count(MultimodalDiagnosticHypothesis),
                "audits": int(self.db.scalar(select(func.count()).select_from(OperationLog).where(
                    OperationLog.module == "multimodal_case"
                )) or 0),
            },
            "providers": {
                "task25c_real_api_allowed": self.settings.TASK25C_ALLOW_REAL_API,
                "ocr_configured": bool(self.settings.OCR_API_ENABLED or self.settings.OCR_ENABLED),
                "vision_configured": bool(self.settings.MIMO_ENABLED or self.settings.CLOUD_VISION_ENABLED),
                "keys_exposed": False,
                "full_provider_response_exposed": False,
            },
            "retrieval": {
                "scope": "chinese_engineering_pilot_r2",
                "partition": "pilot_r5_query_aware",
                "deterministic_fallback": True,
                "dedicated_rerank": "Deferred / Configuration Missing",
                "dedicated_rerank_code": "DEFERRED_QWEN3_RERANK_CONFIG",
                "qwen3_calls": 0,
                "full_reindex_allowed": self.settings.TASK25B_ALLOW_FULL_REINDEX,
            },
            "boundaries": {
                "automatic_sop_approval": False,
                "automatic_formal_task_creation": False,
                "knowledge_approval_modified": False,
                "expert_verified_written": False,
                "vector_partitions_modified": False,
            },
            "benchmark": benchmark or {
                "dataset": "task25c_multimodal_engineering_benchmark_v1",
                "status": "NOT_YET_EVALUATED",
                "expert_verified": False,
            },
            "quality_gate": quality or {"status": "NOT_YET_EVALUATED"},
        }

    def _count(self, model) -> int:
        return int(self.db.scalar(select(func.count()).select_from(model)) or 0)

    def _artifact(self, name: str) -> dict:
        path = self.runtime / name
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}
