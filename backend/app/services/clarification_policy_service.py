from __future__ import annotations

from app.schemas.query_understanding import ClarificationDecision, CompletenessAssessment, QuerySignals, QueryUnderstandingResult
from app.services.clarification_question_template_service import ClarificationQuestionTemplateService


class ClarificationPolicyService:
    QUESTION_MAP = {
        "device_model": "请补充设备的完整型号（例如 SUN2000、LUNA2000 或 SmartLogger 的具体型号）。",
        "specific_symptom_or_alarm_code": "请说明更具体的现象，或提供界面显示的告警代码。",
        "requested_information": "您主要想了解原因、排查步骤、安全要求，还是完成后的验证方法？",
    }

    def decide(
        self,
        *,
        signals: QuerySignals,
        assessment: CompletenessAssessment,
        understanding: QueryUnderstandingResult | None = None,
    ) -> ClarificationDecision:
        high_risk = bool(signals.safety_intent) or any(term in signals.normalized_query for term in ("高压", "带电", "断电", "拆卸", "更换"))
        if understanding and understanding.query_understanding_mode in {
            "FAST_PATH", "DETERMINISTIC", "DETERMINISTIC_WITH_CLARIFICATION",
            "MINIMAX_AMBIGUITY_RESOLUTION", "SAFE_FALLBACK",
        }:
            missing_slots = list(understanding.normalized_semantics.get("missing_slots") or [])
            questions = ClarificationQuestionTemplateService().questions(missing_slots)
            if understanding.clarifying_question and understanding.clarifying_question not in questions:
                questions.insert(0, understanding.clarifying_question)
            status = "CLARIFICATION_REQUIRED" if understanding.needs_clarification else "NO_CLARIFICATION"
            return ClarificationDecision(
                status=status,
                questions=questions[:3],
                missing_information=list(understanding.missing_information),
                suppress_repair_instructions=status == "CLARIFICATION_REQUIRED",
                reason_codes=list(understanding.structured_model_diagnostics.get("reason_codes") or []),
            )
        if assessment.status in {"AMBIGUOUS", "INSUFFICIENT_INFORMATION"}:
            status = "CLARIFICATION_REQUIRED"
        elif assessment.status == "PARTIALLY_SPECIFIED" or (high_risk and not signals.device_models):
            status = "CLARIFICATION_RECOMMENDED"
        else:
            status = "NO_CLARIFICATION"
        missing = list(assessment.missing_information)
        questions: list[str] = []
        for key in ("device_model", "specific_symptom_or_alarm_code", "requested_information"):
            if key in missing and self.QUESTION_MAP[key] not in questions:
                questions.append(self.QUESTION_MAP[key])
        if assessment.ambiguity:
            questions.insert(0, "“没反应”具体是不开机、不发电、指示灯不亮、平台无数据，还是通信中断？")
        if understanding and understanding.clarifying_question and understanding.clarifying_question not in questions:
            questions.append(understanding.clarifying_question)
        questions = questions[:3]
        return ClarificationDecision(
            status=status,
            questions=questions,
            missing_information=missing,
            suppress_repair_instructions=status == "CLARIFICATION_REQUIRED" or high_risk and status != "NO_CLARIFICATION",
            reason_codes=[*assessment.reason_codes, *( ["high_risk_requires_context"] if high_risk and status != "NO_CLARIFICATION" else [])],
        )
