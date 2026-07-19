from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.models import KnowledgeChunk, KnowledgeDocument


@dataclass(slots=True)
class SourceGroundingValidation:
    passed: bool
    unsupported_fields: list[str] = field(default_factory=list)
    source_coverage_ratio: float = 0.0
    source_locator_valid: bool = False
    failures: list[str] = field(default_factory=list)


class SourceGroundingValidator:
    FACT_FIELDS = (
        "symptoms", "conditions", "causes", "actions", "procedure_steps", "prerequisites",
        "verification_steps", "safety_requirements", "communication_terms", "tools", "parts",
        "abort_conditions", "clearance_conditions", "alarm_names", "components",
    )

    def validate(self, unit: dict, chunks: list[KnowledgeChunk], document: KnowledgeDocument) -> SourceGroundingValidation:
        failures: list[str] = []
        unsupported: list[str] = []
        source_ids = [str(chunk.id) for chunk in chunks]
        expected_ids = unit.get("source_chunk_ids") or []
        if not expected_ids or expected_ids != source_ids:
            failures.append("source_chunk_mapping_mismatch")
        if any(str(chunk.document_id) != str(document.id) for chunk in chunks):
            failures.append("source_document_mismatch")
        source = "\n".join((chunk.content or "") for chunk in chunks)
        compact_source = " ".join(source.split())
        hashes = [hashlib.sha256((chunk.content or "").encode("utf-8")).hexdigest() for chunk in chunks]
        if hashes != (unit.get("source_chunk_hashes") or []):
            failures.append("source_hash_mismatch")
        locator = unit.get("source_locator") or {}
        locator_valid = bool(
            locator.get("section")
            and locator.get("heading_path")
            and locator.get("source_chunk_ids") == source_ids
            and locator.get("page_start") is not None
        )
        if not locator_valid:
            failures.append("source_locator_invalid")
        metadata = document.metadata_json or {}
        if metadata.get("normalized_language") != "zh-CN":
            failures.append("language_not_zh_cn")
        if not metadata.get("approved_for_pilot") or not metadata.get("engineering_approved_for_pilot"):
            failures.append("not_approved_for_pilot")
        if document.review_status != "approved" or document.status != "active":
            failures.append("document_not_current_approved")
        if not all(bool((chunk.metadata_json or {}).get("current_chunk_version", True)) for chunk in chunks):
            failures.append("chunk_not_current")
        total_values = supported_values = 0
        for field_name in self.FACT_FIELDS:
            for value in unit.get(field_name) or []:
                total_values += 1
                if " ".join(str(value).split()) in compact_source:
                    supported_values += 1
                else:
                    unsupported.append(f"{field_name}:{str(value)[:80]}")
        for alarm_code in unit.get("alarm_codes") or []:
            total_values += 1
            if str(alarm_code).lower() in compact_source.lower():
                supported_values += 1
            else:
                unsupported.append(f"alarm_codes:{str(alarm_code)[:80]}")
        document_metadata = document.metadata_json or {}
        allowed_models = {
            str(value).lower()
            for value in [document.model, *(document_metadata.get("device_models") or [])]
            if value
        }
        for device_model in unit.get("device_models") or []:
            total_values += 1
            model = str(device_model)
            if model.lower() in compact_source.lower() or model.lower() in allowed_models:
                supported_values += 1
            else:
                unsupported.append(f"device_models:{model[:80]}")
        for span in unit.get("source_spans") or []:
            total_values += 1
            text = " ".join(str(span.get("text") or "").split())
            if text and text in compact_source:
                supported_values += 1
            else:
                unsupported.append("source_span")
        canonical_evidence = str(unit.get("canonical_evidence") or "")
        if not canonical_evidence or " ".join(canonical_evidence.split()) not in compact_source:
            failures.append("canonical_evidence_not_in_source")
        forbidden = ("benchmark", "expected_chunk", "expected_semantic", "case_id")
        if any(value in str(unit.get("canonical_text") or "").lower() for value in forbidden):
            failures.append("benchmark_or_expected_label_leakage")
        coverage = supported_values / total_values if total_values else (1.0 if canonical_evidence else 0.0)
        if unsupported:
            failures.append("unsupported_fields")
        if coverage < 1.0:
            failures.append("source_coverage_below_one")
        return SourceGroundingValidation(
            passed=not failures,
            unsupported_fields=unsupported,
            source_coverage_ratio=round(coverage, 6),
            source_locator_valid=locator_valid,
            failures=list(dict.fromkeys(failures)),
        )
