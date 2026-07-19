from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.schemas.query_understanding import (
    CompletenessAssessment,
    DeterministicUnderstanding,
    MissingSlotV2,
    QuerySignals,
    QueryUnderstandingResult,
    QueryUnderstandingV2Intent,
    RequestedInformationV2,
)
from app.services.query_understanding_merge_service import QueryUnderstandingMergeService


class DeterministicQueryUnderstandingService:
    """Deterministic-first query understanding with no external calls."""

    SYNONYMS: tuple[tuple[str, str], ...] = (
        ("平台没有数据", "监控平台无数据"),
        ("平台没数据", "监控平台无数据"),
        ("手机没有数据", "手机端无数据"),
        ("手机没数据", "手机端无数据"),
        ("连不上", "连接失败"),
        ("不出力", "无功率输出"),
        ("不发电", "无功率输出"),
        ("灯不亮", "指示灯不亮"),
        ("总掉线", "通信中断"),
        ("老是掉线", "通信中断"),
        ("掉线", "通信中断"),
        ("晚上", "夜间"),
        ("晚间", "夜间"),
        ("白天又好了", "白天恢复正常"),
        ("白天正常了", "白天恢复正常"),
        ("机器", "设备"),
        ("咋办", "怎么办"),
        ("咋整", "怎么办"),
    )
    INTENT_REQUEST: dict[QueryUnderstandingV2Intent, RequestedInformationV2] = {
        "CAUSE": "CAUSE",
        "TROUBLESHOOTING": "ACTION",
        "PROCEDURE": "PROCEDURE",
        "SAFETY": "SAFETY",
        "ALARM": "ALARM_MEANING",
        "PREREQUISITE": "PREREQUISITE",
        "VERIFICATION": "VERIFICATION",
        "COMMUNICATION": "GENERAL_INFORMATION",
        "GENERAL": "GENERAL_INFORMATION",
    }
    SLOT_TO_LEGACY = QueryUnderstandingMergeService.SLOT_TO_LEGACY

    def understand(
        self,
        *,
        signals: QuerySignals,
        assessment: CompletenessAssessment,
        conversation_state: dict[str, Any] | None = None,
    ) -> DeterministicUnderstanding:
        merged = QueryUnderstandingMergeService().merge_signals(signals, conversation_state=conversation_state)
        query = merged.normalized_query
        provisional_intent = self._intent(query, merged)
        requested = self._requested(provisional_intent, merged)
        intent = self._primary_intent(query, merged, requested, provisional_intent)
        requested = self._requested(intent, merged)
        missing = self._missing_slots(query, merged, intent, requested, assessment)
        ambiguous = any(term in query for term in ("没反应", "不工作", "设备异常", "机器异常", "不正常", "有问题", "坏了"))
        ambiguity = "AMBIGUOUS" if ambiguous else "INSUFFICIENT" if self._insufficient(query, merged) else "PARTIAL" if missing else "CLEAR"
        needs_clarification = bool(missing and ambiguity in {"AMBIGUOUS", "INSUFFICIENT", "PARTIAL"})
        canonical = self.canonicalize(query, intent=intent, requested=requested)
        confidence = self._confidence(ambiguity, intent, merged, needs_clarification)
        reasons = [f"intent_rule_{intent.lower()}", "deterministic_canonicalization_v1"]
        if ambiguous:
            reasons.append("fixed_dictionary_ambiguity")
        if missing:
            reasons.extend(f"missing_{slot.lower()}" for slot in missing)
        if conversation_state:
            reasons.append("conversation_facts_merged")
        return DeterministicUnderstanding(
            intent=intent,
            canonical_query=canonical,
            requested_information=requested,
            confirmed_facts=self._facts(merged),
            normalized_symptoms=self._normalized_symptoms(merged),
            normalized_components=list(merged.components),
            normalized_conditions=list(dict.fromkeys([*merged.time_conditions, *merged.operating_states])),
            ambiguity=ambiguity,
            missing_slots=missing,
            needs_clarification=needs_clarification,
            confidence=confidence,
            reason_codes=list(dict.fromkeys(reasons))[:12],
        )

    def to_result(
        self,
        *,
        deterministic: DeterministicUnderstanding,
        signals: QuerySignals,
        assessment: CompletenessAssessment,
        conversation_state: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        merged = QueryUnderstandingMergeService().merge_signals(signals, conversation_state=conversation_state)
        mode = "DETERMINISTIC_WITH_CLARIFICATION" if deterministic.needs_clarification else (
            "FAST_PATH" if self._fast_path(deterministic, merged) else "DETERMINISTIC"
        )
        missing_legacy = [self.SLOT_TO_LEGACY[slot] for slot in deterministic.missing_slots]
        result = QueryUnderstandingResult(
            request_id=f"dur4_{uuid4().hex}",
            original_query=str((conversation_state or {}).get("original_query") or signals.original_query),
            normalized_query=signals.normalized_query,
            canonical_question=deterministic.canonical_query,
            primary_intent=deterministic.intent,
            confirmed_facts=deterministic.confirmed_facts,
            normalized_semantics={
                "canonical_query": deterministic.canonical_query,
                "symptoms": deterministic.normalized_symptoms,
                "components": deterministic.normalized_components,
                "conditions": deterministic.normalized_conditions,
                "requested_information": deterministic.requested_information,
                "ambiguity": deterministic.ambiguity,
                "missing_slots": deterministic.missing_slots,
                "reason_codes": deterministic.reason_codes,
            },
            device_models=list(merged.device_models),
            product_families=QueryUnderstandingMergeService._unique([
                merged.product_family, *QueryUnderstandingMergeService._families(merged.device_models),
            ]),
            equipment_categories=QueryUnderstandingMergeService._equipment_categories(merged.device_models),
            components=deterministic.normalized_components,
            symptoms=deterministic.normalized_symptoms,
            conditions=deterministic.normalized_conditions,
            alarm_codes=list(merged.alarm_codes),
            alarm_names=list(merged.alarm_names),
            requested_information=list(deterministic.requested_information),
            missing_information=missing_legacy,
            ambiguity=deterministic.ambiguity in {"AMBIGUOUS", "INSUFFICIENT"},
            needs_clarification=deterministic.needs_clarification,
            confidence=deterministic.confidence,
            model_provider="deterministic",
            model_name="deterministic_query_understanding_v1",
            prompt_version="task25b_r3_dev_r5_r4_mm_deterministic_v1",
            completeness_status={"CLEAR": "CLEAR", "PARTIAL": "PARTIALLY_SPECIFIED", "AMBIGUOUS": "AMBIGUOUS", "INSUFFICIENT": "INSUFFICIENT_INFORMATION"}[deterministic.ambiguity],
            fast_path=mode == "FAST_PATH",
            # Compatibility field denotes the non-fast understanding stage;
            # FAST_PATH still performs deterministic signal extraction but no
            # model-backed or extended understanding call.
            query_understanding_used=mode != "FAST_PATH",
            structured_model_diagnostics={
                "external_call_count": 0,
                "reason_codes": deterministic.reason_codes,
                "missing_slots": deterministic.missing_slots,
            },
            query_understanding_mode=mode,
            requested_provider="deterministic",
            actual_provider="deterministic",
        )
        return result

    @classmethod
    def canonicalize(
        cls,
        query: str,
        *,
        intent: QueryUnderstandingV2Intent,
        requested: list[RequestedInformationV2],
    ) -> str:
        value = query.strip()
        for source, target in cls.SYNONYMS:
            value = value.replace(source, target)
        value = re.sub(r"[？?！!。]+$", "", value)
        value = re.sub(r"[，,；;]+", "，", value)
        value = re.sub(r"\s+", " ", value).strip(" ，")
        suffixes = {
            "CAUSE": "查询可能原因",
            "TROUBLESHOOTING": "查询排查方法",
            "PROCEDURE": "查询操作步骤",
            "SAFETY": "查询安全要求",
            "ALARM": "查询告警含义",
            "PREREQUISITE": "查询操作前提",
            "VERIFICATION": "查询恢复验证方法",
        }
        suffix = (
            "查询可能原因和排查方法"
            if intent == "TROUBLESHOOTING" and "CAUSE" in requested and "ACTION" in requested
            else suffixes.get(intent)
        )
        if suffix and not any(token in value for token in ("查询可能原因", "查询排查方法", "查询操作步骤", "查询安全要求", "查询告警含义", "查询操作前提", "查询恢复验证方法")):
            value = re.sub(r"(?:为什么|为何|什么原因|啥原因|原因是什么|怎么回事)$", "", value).strip(" ，")
            value = re.sub(r"(?:怎么办|怎么处理|如何处理|如何排查|怎么排查|怎么解决|怎么查)$", "", value).strip(" ，")
            value = f"{value}，{suffix}" if value else suffix
        return value[:512]

    @staticmethod
    def _intent(query: str, signals: QuerySignals) -> QueryUnderstandingV2Intent:
        # User-request suffixes have priority over diagnostic words quoted from
        # a long field description. These are domain phrases, never case IDs.
        if any(term in query for term in ("处理完以后咋确认", "处理完以后如何确认", "完成后咋确认")):
            return "VERIFICATION"
        if any(term in query for term in ("之前要注意哪些安全风险", "之前要注意什么安全风险")):
            return "SAFETY"
        if any(term in query for term in ("之前得先满足哪些条件", "之前要先满足哪些条件")):
            return "PREREQUISITE"
        if any(term in query for term in ("具体按什么顺序操作", "按什么顺序操作")):
            return "PROCEDURE"
        if any(term in query for term in ("咋排查处理", "先查啥", "先查什么", "该从哪儿查", "应检查什么")):
            return "COMMUNICATION" if signals.communication_terms and "先查" in query else "TROUBLESHOOTING"
        if any(term in query for term in ("安全", "风险", "危险", "带电", "触电", "防护", "注意什么", "注意事项")):
            return "SAFETY"
        if any(term in query for term in ("操作前", "开始前", "前提", "前置", "准备什么", "需要准备", "先做什么", "先满足")):
            return "PREREQUISITE"
        if any(term in query for term in ("怎么确认", "如何确认", "如何验证", "怎么验证", "是否恢复", "恢复了吗", "是否正常", "确认恢复")):
            return "VERIFICATION"
        if any(term in query for term in (
            "步骤", "怎么操作", "如何操作", "如何更换", "更换流程", "如何配置", "配置流程", "按顺序",
            "操作流程", "如何恢复", "如何回收",
        )):
            return "PROCEDURE"
        if any(term in query for term in ("为什么", "为何", "啥原因", "什么原因", "原因", "怎么回事", "什么导致")):
            return "CAUSE"
        if any(term in query for term in (
            "怎么办", "怎么处理", "如何处理", "如何排查", "怎么排查", "咋排查", "怎么解决", "怎么修",
            "排查", "怎么查", "先查啥", "先查什么", "该从哪儿查", "应检查什么",
        )):
            return "TROUBLESHOOTING"
        if (signals.alarm_codes or signals.alarm_names or "告警" in query or "报警" in query or "故障码" in query) and any(
            term in query for term in ("什么意思", "含义", "是什么", "解释")
        ):
            return "ALARM"
        if signals.communication_terms or any(term.lower() in query.lower() for term in ("wifi", "wlan", "rs485", "modbus", "4g", "以太网", "无数据")):
            return "COMMUNICATION"
        return "GENERAL"

    @staticmethod
    def _primary_intent(
        query: str,
        signals: QuerySignals,
        requested: list[RequestedInformationV2],
        provisional: QueryUnderstandingV2Intent,
    ) -> QueryUnderstandingV2Intent:
        """Select one routing task without discarding the user's information set."""
        requested_set = set(requested)
        if "PROCEDURE" in requested_set:
            return "PROCEDURE"
        if {"PREREQUISITE", "VERIFICATION"}.issubset(requested_set):
            return "PROCEDURE"
        if "ACTION" in requested_set and (
            "CAUSE" in requested_set or "CONFIGURATION" in requested_set
            or provisional in {"COMMUNICATION", "TROUBLESHOOTING"}
        ):
            return "TROUBLESHOOTING"
        if "CONFIGURATION" in requested_set:
            return "PROCEDURE"
        if "CAUSE" in requested_set:
            return "CAUSE"
        if "ALARM_MEANING" in requested_set:
            return "ALARM"
        if requested_set == {"SAFETY"}:
            return "SAFETY"
        if requested_set == {"PREREQUISITE"}:
            return "PREREQUISITE"
        if requested_set == {"VERIFICATION"}:
            return "VERIFICATION"
        return provisional

    @classmethod
    def _requested(cls, intent: QueryUnderstandingV2Intent, signals: QuerySignals) -> list[RequestedInformationV2]:
        output: list[RequestedInformationV2] = []
        mapping: dict[str, RequestedInformationV2] = {
            "CAUSE": "CAUSE", "ACTION": "ACTION", "PROCEDURE": "PROCEDURE", "SAFETY": "SAFETY",
            "PREREQUISITE": "PREREQUISITE", "VERIFICATION": "VERIFICATION", "CONFIGURATION": "CONFIGURATION",
        }
        for item in signals.requested_information:
            if item in mapping:
                output.append(mapping[item])
        if intent == "ALARM":
            output.append("ALARM_MEANING")
        elif not output and intent not in {"COMMUNICATION", "GENERAL"}:
            output.append(cls.INTENT_REQUEST[intent])
        if (
            intent == "TROUBLESHOOTING"
            and signals.communication_terms
            and len(signals.time_conditions) >= 2
            and "CAUSE" not in output
        ):
            output.insert(0, "CAUSE")
        query = signals.normalized_query
        if intent == "PROCEDURE" and ({"PREREQUISITE", "VERIFICATION"} & set(output)) and "ACTION" not in output:
            output.append("ACTION")
        if intent == "PROCEDURE" and any(term in query for term in ("更换", "拆卸", "安装", "熔丝")) and "SAFETY" not in output:
            output.append("SAFETY")
        if intent == "TROUBLESHOOTING" and not output:
            output.append("ACTION")
        return list(dict.fromkeys(output))[:5]

    @staticmethod
    def _missing_slots(
        query: str,
        signals: QuerySignals,
        intent: QueryUnderstandingV2Intent,
        requested: list[RequestedInformationV2],
        assessment: CompletenessAssessment,
    ) -> list[MissingSlotV2]:
        missing: list[MissingSlotV2] = []
        ambiguous = any(term in query for term in ("没反应", "不工作", "设备异常", "机器异常", "不正常", "有问题", "坏了"))
        generic_symptoms = {"没反应", "异常", "状态异常", "故障", "告警"}
        has_specific_symptom = any(item not in generic_symptoms for item in signals.symptoms)
        if ambiguous and not has_specific_symptom:
            missing.append("SPECIFIC_SYMPTOM")
        generic_alarm = ("告警" in query or "报警" in query or "故障码" in query) and not (signals.alarm_codes or signals.alarm_names)
        if generic_alarm and intent in {"ALARM", "CAUSE", "TROUBLESHOOTING", "VERIFICATION"}:
            missing.append("ALARM_CODE")
        if not requested and intent in {"GENERAL", "COMMUNICATION"} and not any(
            term in query for term in ("是什么", "什么意思", "怎么", "如何", "为什么", "原因", "步骤", "安全")
        ):
            missing.append("REQUESTED_ACTION")
        if len(query.strip()) < 4 or assessment.status == "INSUFFICIENT_INFORMATION" and not signals.communication_terms:
            if not signals.symptoms and not signals.alarm_codes and not signals.alarm_names:
                missing.append("SPECIFIC_SYMPTOM")
            if not requested:
                missing.append("REQUESTED_ACTION")
        return list(dict.fromkeys(missing))[:4]

    @staticmethod
    def _insufficient(query: str, signals: QuerySignals) -> bool:
        return len(query.strip()) < 4 or not bool(
            signals.device_models or signals.alarm_codes or signals.alarm_names or signals.symptoms
            or signals.communication_terms or signals.components or signals.requested_information
        )

    @staticmethod
    def _confidence(ambiguity: str, intent: str, signals: QuerySignals, clarify: bool) -> float:
        if ambiguity == "CLEAR" and intent != "GENERAL":
            return 0.97 if signals.device_models or signals.alarm_codes else 0.95
        if ambiguity == "PARTIAL" and not clarify:
            return 0.91
        if ambiguity == "AMBIGUOUS":
            return 0.55
        return 0.62 if clarify else 0.82

    @staticmethod
    def _facts(signals: QuerySignals) -> dict[str, Any]:
        return {
            "manufacturer": signals.manufacturer,
            "product_family": signals.product_family,
            "model": signals.model,
            "model_original": signals.model_original,
            "alarm_code": signals.alarm_code,
            "fault_type": signals.fault_type,
            "maintenance_intent": signals.maintenance_intent,
            "safety_risk": signals.safety_risk,
            "device_models": list(signals.device_models),
            "alarm_codes": list(signals.alarm_codes),
            "alarm_names": list(signals.alarm_names),
            "components": list(signals.components),
            "symptoms": list(signals.symptoms),
            "conditions": [*signals.time_conditions, *signals.operating_states],
            "numbers": list(signals.numbers),
            "negative_expressions": list(signals.negative_expressions),
            "communication_terms": list(signals.communication_terms),
        }

    @classmethod
    def _normalized_symptoms(cls, signals: QuerySignals) -> list[str]:
        output = []
        for symptom in signals.symptoms:
            value = symptom
            for source, target in cls.SYNONYMS:
                value = value.replace(source, target)
            output.append(value)
        return list(dict.fromkeys(output))

    @staticmethod
    def _fast_path(understanding: DeterministicUnderstanding, signals: QuerySignals) -> bool:
        return not understanding.needs_clarification and bool(
            (signals.alarm_codes or signals.alarm_names)
            and understanding.intent == "ALARM"
            and set(understanding.requested_information) <= {"ALARM_MEANING"}
        )
