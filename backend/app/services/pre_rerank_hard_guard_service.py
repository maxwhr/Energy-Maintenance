from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.schemas.query_understanding import QueryUnderstandingResult
from app.services.rrf_fusion_service import QueryAwareCandidate


@dataclass(frozen=True, slots=True)
class PreRerankHardGuardResult:
    candidates: list[QueryAwareCandidate]
    diagnostics: dict[str, Any]


class PreRerankHardGuardService:
    """Remove only explicit boundary violations before any model ranking."""

    MODEL_RE = re.compile(r"(?:SUN2000|LUNA2000|SmartLogger|SG)[A-Z0-9()/_.-]*", re.I)
    ALARM_RE = re.compile(r"(?:告警|故障(?:码)?)[：:\s-]*([A-Z]{0,4}\d{3,6})", re.I)
    INACTIVE_STATUSES = {"INACTIVE", "PENDING", "PENDING_REVIEW", "SUPERSEDED", "REJECTED", "DELETED"}

    def apply(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
    ) -> PreRerankHardGuardResult:
        kept: list[QueryAwareCandidate] = []
        seen: set[str] = set()
        removals: list[dict[str, str]] = []
        for item in candidates:
            reason = self._rejection_reason(item, understanding)
            identity = item.evidence_equivalence_key or item.evidence_identity or item.semantic_unit_id or item.candidate_id
            if reason is None and identity in seen:
                reason = "DUPLICATE_EVIDENCE_IDENTITY"
            if reason is not None:
                removals.append({"candidate_id": item.candidate_id, "reason": reason})
                continue
            seen.add(identity)
            kept.append(item)
        return PreRerankHardGuardResult(
            candidates=kept,
            diagnostics={
                "executed": True,
                "candidates_in": len(candidates),
                "candidates_out": len(kept),
                "removed_count": len(removals),
                "removals": removals,
                "scope_validation_passed": all(item.scope_validation_passed for item in kept),
                "benchmark_labels_used": False,
                "candidate_body_mutated": False,
                "source_mutated": False,
            },
        )

    def _rejection_reason(
        self,
        item: QueryAwareCandidate,
        understanding: QueryUnderstandingResult,
    ) -> str | None:
        if not item.scope_validation_passed:
            return "SCOPE_VALIDATION_FAILED"
        metadata = self._metadata(item)
        status = str(
            metadata.get("index_status") or metadata.get("review_status") or metadata.get("status") or ""
        ).upper()
        if status in self.INACTIVE_STATUSES:
            return "INACTIVE_OR_UNAPPROVED_EVIDENCE"
        if metadata.get("current_document_version") is False or metadata.get("superseded") is True:
            return "SUPERSEDED_EVIDENCE"
        expected_models = {
            value.upper()
            for value in understanding.device_models
            if re.sub(r"[^A-Z0-9]", "", value.upper()) != "SUN2000"
        }
        candidate_models = self._values(metadata, "device_models", "device_model", "applicable_device_models")
        if not candidate_models:
            candidate_models = {value.upper() for value in self.MODEL_RE.findall(item.content or "")}
        if expected_models and candidate_models and expected_models.isdisjoint(candidate_models) and not item.exact_model_match:
            return "EXPLICIT_WRONG_MODEL"
        expected_alarms = {value.upper() for value in understanding.alarm_codes}
        candidate_alarms = self._values(metadata, "alarm_codes", "alarm_code")
        if not candidate_alarms:
            candidate_alarms = {value.upper() for value in self.ALARM_RE.findall(item.content or "")}
        if expected_alarms and candidate_alarms and expected_alarms.isdisjoint(candidate_alarms) and not item.exact_alarm_match:
            return "EXPLICIT_WRONG_ALARM"
        return None

    @staticmethod
    def _metadata(item: QueryAwareCandidate) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for source in (getattr(item.document, "metadata_json", None), getattr(item.chunk, "metadata_json", None)):
            if isinstance(source, dict):
                output.update(source)
        semantic = output.get("semantic_unit")
        if isinstance(semantic, dict):
            output = {**output, **semantic}
        return output

    @staticmethod
    def _values(metadata: dict[str, Any], *keys: str) -> set[str]:
        values: set[str] = set()
        for key in keys:
            value = metadata.get(key)
            items = value if isinstance(value, list) else [value] if value else []
            values.update(str(item).strip().upper() for item in items if str(item).strip())
        return values
