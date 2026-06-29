from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import DeviceMaintenanceRecord
from app.schemas.diagnosis import DiagnosisRelatedHistory


@dataclass
class RecurrenceResult:
    is_recurrent: bool
    related_history: list[DiagnosisRelatedHistory]
    recurrent_reference_record_id: str | None


class RecurrenceService:
    def evaluate(
        self,
        *,
        device_id: object | None,
        fault_type: str | None,
        alarm_code: str | None,
        fault_description: str,
        keywords: list[str],
        history_records: list[DeviceMaintenanceRecord],
    ) -> RecurrenceResult:
        if not device_id:
            return RecurrenceResult(False, [], None)

        scored: list[tuple[float, DeviceMaintenanceRecord]] = []
        for record in history_records:
            score = self._score_record(
                record=record,
                fault_type=fault_type,
                alarm_code=alarm_code,
                fault_description=fault_description,
                keywords=keywords,
            )
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)

        related = [
            self._history_payload(record, is_recurrent=score >= 6.0)
            for score, record in scored[:3]
        ]
        is_recurrent = any(item.is_recurrent for item in related)
        reference_id = str(related[0].record_id) if is_recurrent and related else None
        return RecurrenceResult(is_recurrent, related, reference_id)

    def _score_record(
        self,
        *,
        record: DeviceMaintenanceRecord,
        fault_type: str | None,
        alarm_code: str | None,
        fault_description: str,
        keywords: list[str],
    ) -> float:
        score = 0.0
        if fault_type and record.fault_type == fault_type:
            score += 8.0
        if alarm_code and record.alarm_code and record.alarm_code.lower() == alarm_code.lower():
            score += 8.0

        text = " ".join(
            [
                record.fault_description or "",
                record.root_cause or "",
                record.repair_action or "",
                record.verification_result or "",
            ]
        )
        for keyword in keywords[:50]:
            if len(keyword) < 2:
                continue
            if self._contains(text, keyword):
                score += 1.2
        for keyword in self._extract_keywords(fault_description)[:20]:
            if self._contains(text, keyword):
                score += 1.0
        return score

    @staticmethod
    def _contains(text: str, keyword: str) -> bool:
        return keyword.lower() in text.lower()

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9][A-Za-z0-9_\-./]*", text)
        seen: set[str] = set()
        unique: list[str] = []
        for term in terms:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                unique.append(term)
        return unique

    @staticmethod
    def _history_payload(record: DeviceMaintenanceRecord, *, is_recurrent: bool) -> DiagnosisRelatedHistory:
        return DiagnosisRelatedHistory(
            record_id=record.id,
            device_id=record.device_id,
            fault_type=record.fault_type,
            alarm_code=record.alarm_code,
            fault_description=record.fault_description,
            root_cause=record.root_cause,
            repair_action=record.repair_action,
            verification_result=record.verification_result,
            is_recurrent=is_recurrent or record.is_recurrent,
            completed_at=record.completed_at,
        )
