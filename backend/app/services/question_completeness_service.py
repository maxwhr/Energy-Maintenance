from __future__ import annotations

from app.schemas.query_understanding import CompletenessAssessment, QuerySignals


class QuestionCompletenessService:
    AMBIGUOUS_PHRASES = ("设备没反应", "机器没反应", "设备不工作", "设备异常", "有问题", "不正常", "坏了")
    AMBIGUITY_OPTIONS = ("不发电", "不开机", "指示灯不亮", "平台无数据", "通信中断", "屏幕无显示")

    def assess(self, signals: QuerySignals) -> CompletenessAssessment:
        query = signals.normalized_query
        meaningful_symptoms = [item for item in signals.symptoms if item not in {"异常", "故障", "告警"}]
        ambiguity = any(value in query for value in self.AMBIGUOUS_PHRASES)
        missing: list[str] = []
        reasons: list[str] = []
        if not signals.device_models:
            missing.append("device_model")
        if not signals.alarm_codes and not signals.alarm_names and not meaningful_symptoms:
            missing.append("specific_symptom_or_alarm_code")
        if not signals.requested_information:
            missing.append("requested_information")
        if ambiguity:
            reasons.append("generic_no_response_has_multiple_interpretations")
            return CompletenessAssessment(
                status="AMBIGUOUS",
                missing_information=list(dict.fromkeys(missing)),
                ambiguity=True,
                ambiguity_options=list(self.AMBIGUITY_OPTIONS),
                reason_codes=reasons,
            )
        actionable_focus = bool(
            signals.alarm_codes
            or signals.alarm_names
            or signals.device_models
            or meaningful_symptoms
            or signals.communication_terms
            or signals.components
            or signals.requested_information
        )
        if len(query) < 4 or not actionable_focus:
            reasons.append("no_actionable_device_or_fault_signal")
            return CompletenessAssessment(
                status="INSUFFICIENT_INFORMATION",
                missing_information=list(dict.fromkeys(missing)),
                reason_codes=reasons,
            )
        if signals.alarm_codes or signals.alarm_names or (signals.device_models and meaningful_symptoms and signals.requested_information):
            return CompletenessAssessment(status="CLEAR", missing_information=[], reason_codes=["sufficient_explicit_signals"])
        reasons.append("retrieval_possible_but_context_incomplete")
        return CompletenessAssessment(
            status="PARTIALLY_SPECIFIED",
            missing_information=list(dict.fromkeys(missing)),
            reason_codes=reasons,
        )
