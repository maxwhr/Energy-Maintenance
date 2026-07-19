from __future__ import annotations

from app.schemas.query_understanding import (
    AmbiguityInterpretation,
    DeterministicUnderstanding,
    QuerySignals,
)


class AmbiguityOptionGeneratorService:
    """Generate bounded interpretations from a fixed PV-maintenance dictionary."""

    AMBIGUOUS_PHRASES = ("没反应", "不工作", "设备异常", "机器异常", "不正常", "有问题", "坏了")

    def generate(
        self,
        *,
        signals: QuerySignals,
        understanding: DeterministicUnderstanding,
    ) -> list[AmbiguityInterpretation]:
        query = signals.normalized_query
        if understanding.ambiguity not in {"AMBIGUOUS", "INSUFFICIENT"}:
            return []
        if not any(term in query for term in self.AMBIGUOUS_PHRASES):
            return []

        explicit_focus = bool(
            signals.alarm_codes
            or signals.alarm_names
            or [item for item in signals.symptoms if item not in {"没反应", "异常", "故障", "告警"}]
        )
        if explicit_focus:
            return []

        shared = [*signals.device_models, *signals.time_conditions, *signals.operating_states]
        prefix = f"{' '.join(signals.device_models)} " if signals.device_models else "设备"
        raw = [
            ("TROUBLESHOOTING", f"{prefix}无法上电", ["SPECIFIC_SYMPTOM"], "POWER_ON"),
            ("TROUBLESHOOTING", f"{prefix}没有功率输出", ["SPECIFIC_SYMPTOM"], "POWER_OUTPUT"),
            ("COMMUNICATION", f"{prefix}平台或手机无法通信", ["SPECIFIC_SYMPTOM", "COMMUNICATION_METHOD"], "COMMUNICATION"),
            ("TROUBLESHOOTING", f"{prefix}指示灯或显示屏没有显示", ["SPECIFIC_SYMPTOM"], "DISPLAY"),
        ]
        if "没反应" not in query:
            raw = raw[:3]
        base_confidence = 0.52 if "没反应" in query else 0.48
        return [
            AmbiguityInterpretation(
                interpretation_id=f"i{index}",
                intent=intent,
                canonical_query=canonical.strip(),
                required_slots=slots,
                supporting_signals=list(dict.fromkeys([*shared, reason.lower()])),
                confidence=max(0.0, base_confidence - index * 0.01),
                reason_codes=[f"fixed_domain_ambiguity_{reason.lower()}"],
            )
            for index, (intent, canonical, slots, reason) in enumerate(raw[:4])
        ]
