from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field


def normalize_device_model(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").upper().strip()
    normalized = re.sub(r"[‐‑‒–—−]", "-", normalized)
    return re.sub(r"\s+", "", normalized)


def normalize_alarm_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").upper().strip()
    normalized = re.sub(r"[‐‑‒–—−_]", "-", normalized)
    return re.sub(r"\s+", "", normalized)


def normalize_fault_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").lower().strip()
    return re.sub(r"[^0-9a-z\u3400-\u4dbf\u4e00-\u9fff]+", "", normalized)


@dataclass(slots=True)
class QueryUnderstanding:
    normalized_query: str
    query_intent: str
    device_models: list[str] = field(default_factory=list)
    fault_codes: list[str] = field(default_factory=list)
    fault_names: list[str] = field(default_factory=list)
    component_terms: list[str] = field(default_factory=list)
    symptom_terms: list[str] = field(default_factory=list)
    safety_terms: list[str] = field(default_factory=list)
    time_terms: list[str] = field(default_factory=list)
    document_type_filters: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    kg_alias_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def model_dump(self) -> dict:
        return asdict(self)


class QueryUnderstandingService:
    MODEL_PATTERN = re.compile(r"(?:SUN2000(?:[-(][A-Z0-9/()\-]+)?|LUNA2000(?:[-(][A-Z0-9/()\-]+)?|SmartLogger\d*|SG\d+[A-Z0-9-]*|FusionSolar)", re.I)
    FAULT_PATTERN = re.compile(r"\b(?:[A-Z]{1,4}[-_]?)?\d{3,6}\b", re.I)
    ALIASES = {
        "绝缘低": ["绝缘阻抗低", "低绝缘电阻", "low insulation resistance"],
        "掉线": ["设备离线", "通信中断", "device offline"],
        "过温": ["温度过高", "over temperature", "散热异常"],
        "逆变器": ["光伏逆变器", "pv inverter"],
        "直流侧": ["DC侧", "光伏组串"],
        "交流侧": ["AC侧", "电网侧"],
    }
    COMPONENTS = ("风扇", "MPPT", "组串", "直流侧", "交流侧", "通信模块", "电网", "散热器", "接地")
    SYMPTOMS = ("离线", "掉线", "过温", "告警", "低发电", "无输出", "跳闸", "异常", "绝缘低", "通信中断")
    SAFETY = ("高压", "触电", "断电", "验电", "放电", "接地", "安全", "PPE", "锁定挂牌")
    TIME_TERMS = ("最近", "今天", "昨日", "间歇", "持续", "启动时", "并网时", "雨后", "夜间")
    FAULT_NAMES = ("绝缘阻抗低", "电网过压", "电网欠压", "过温", "通信中断", "设备离线", "风扇故障", "组串异常", "直流异常", "并网故障")

    # Canonical UTF-8 vocabulary used for real Chinese request text.  The older
    # compatibility literals remain above for historical data, while this tuple
    # prevents mojibake source literals from disabling semantic routing.
    CHINESE_COMPONENTS = ("风扇", "MPPT", "组串", "直流侧", "交流侧", "通信模块", "电网", "散热器", "接地", "电池")
    CHINESE_SYMPTOMS = ("离线", "掉线", "过温", "告警", "低发电", "无输出", "跳闸", "异常", "绝缘低", "通信中断", "降额")
    CHINESE_SAFETY = ("高压", "触电", "断电", "验电", "放电", "接地", "安全", "PPE", "锁定挂牌")
    CHINESE_FAULT_NAMES = ("绝缘阻抗低", "电网过压", "电网欠压", "过温", "通信中断", "设备离线", "风扇故障", "组串异常", "直流异常", "并网故障")
    CHINESE_ALIASES = {
        "绝缘低": ("绝缘阻抗低", "低绝缘电阻", "low insulation resistance"),
        "掉线": ("设备离线", "通信中断", "device offline"),
        "过温": ("温度过高", "over temperature", "散热异常"),
        "逆变器": ("光伏逆变器", "pv inverter"),
        "直流侧": ("DC侧", "光伏组串"),
        "交流侧": ("AC侧", "电网侧"),
    }

    def understand(self, query: str) -> QueryUnderstanding:
        original = unicodedata.normalize("NFKC", query or "").strip()
        normalized = re.sub(r"\s+", " ", original)
        if not normalized:
            raise ValueError("query must not be empty")
        model_matches = list(self.MODEL_PATTERN.finditer(normalized))
        models = self._unique(normalize_device_model(match.group(0)) for match in model_matches)
        model_spans = [match.span() for match in model_matches]
        fault_codes = self._unique(
            normalize_alarm_identifier(match.group(0))
            for match in self.FAULT_PATTERN.finditer(normalized)
            if not any(start <= match.start() and match.end() <= end for start, end in model_spans)
        )
        components = self._matches(normalized, self.COMPONENTS)
        symptoms = self._matches(normalized, self.SYMPTOMS)
        safety = self._matches(normalized, self.SAFETY)
        time_terms = self._matches(normalized, self.TIME_TERMS)
        fault_names = self._matches(normalized, self.FAULT_NAMES)
        components = self._unique([*components, *self._matches(normalized, self.CHINESE_COMPONENTS)])
        symptoms = self._unique([*symptoms, *self._matches(normalized, self.CHINESE_SYMPTOMS)])
        safety = self._unique([*safety, *self._matches(normalized, self.CHINESE_SAFETY)])
        fault_names = self._unique([*fault_names, *self._matches(normalized, self.CHINESE_FAULT_NAMES)])
        negative = self._unique(re.findall(r"(?:不要|排除|不是|无)([\w\u4e00-\u9fff-]{2,20})", normalized))
        aliases: list[str] = []
        for term, values in self.ALIASES.items():
            if term.lower() in normalized.lower() or any(value.lower() in normalized.lower() for value in values):
                aliases.extend(values)
        for term, values in self.CHINESE_ALIASES.items():
            if term.lower() in normalized.lower() or any(value.lower() in normalized.lower() for value in values):
                aliases.extend(values)
        document_filters = self._document_filters(normalized)
        intent = self._intent(normalized, fault_codes, fault_names, models, safety)
        expanded = self._unique([*models, *fault_codes, *fault_names, *components, *symptoms, *aliases])
        evidence = sum(bool(items) for items in (models, fault_codes, components, symptoms, aliases, document_filters))
        return QueryUnderstanding(
            normalized_query=normalized,
            query_intent=intent,
            device_models=models,
            fault_codes=fault_codes,
            fault_names=fault_names,
            component_terms=components,
            symptom_terms=symptoms,
            safety_terms=safety,
            time_terms=time_terms,
            document_type_filters=document_filters,
            expanded_terms=expanded,
            kg_alias_terms=self._unique(aliases),
            negative_terms=negative,
            confidence=round(min(0.98, 0.55 + 0.07 * evidence), 2),
        )

    @staticmethod
    def _intent(query: str, fault_codes: list[str], fault_names: list[str], models: list[str], safety: list[str]) -> str:
        if any(term.lower() in query.lower() for term in ("图片", "图像", "视觉", "铭牌", "告警屏", "OCR", "照片")):
            return "visual_descriptor_query"
        if any(term in query for term in ("步骤", "处理", "排查", "检修", "怎么", "检查")) and not fault_codes and not models:
            return "fault_diagnosis"
        if any(term.lower() in query.lower() for term in ("图片", "图像", "视觉", "铭牌", "告警屏", "OCR", "照片")):
            return "visual_descriptor_query"
        if fault_codes or fault_names:
            return "alarm_code_query"
        if safety:
            return "safety_operation"
        if any(term in query for term in ("步骤", "处理", "排查", "检修", "怎么")):
            return "fault_diagnosis"
        if models:
            return "device_model_query"
        return "maintenance_knowledge_query"

    @staticmethod
    def _document_filters(query: str) -> list[str]:
        mapping = {
            "手册": "manual", "告警码": "alarm_code", "故障码": "alarm_code",
            "规程": "sop", "步骤": "sop", "案例": "fault_case", "巡检": "inspection_standard",
            "检修记录": "maintenance_record",
        }
        return QueryUnderstandingService._unique(value for key, value in mapping.items() if key in query)

    @staticmethod
    def _matches(query: str, vocabulary: tuple[str, ...]) -> list[str]:
        lowered = query.lower()
        return [term for term in vocabulary if term.lower() in lowered]

    @staticmethod
    def _unique(values) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                result.append(cleaned)
        return result
