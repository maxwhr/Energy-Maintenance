from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.retrieval import RetrievalQueryRequest


DOMAIN_TERMS = [
    "华为",
    "阳光",
    "阳光电源",
    "SUN2000",
    "FusionSolar",
    "Sungrow",
    "SG",
    "光伏",
    "逆变器",
    "组串",
    "组件",
    "并网",
    "告警",
    "告警码",
    "故障",
    "异常",
    "排查",
    "检修",
    "巡检",
    "绝缘",
    "绝缘阻抗",
    "对地绝缘",
    "绝缘低",
    "漏电",
    "接地",
    "直流",
    "交流",
    "电网",
    "电压",
    "频率",
    "过压",
    "欠压",
    "过温",
    "温度高",
    "散热",
    "风扇",
    "通风",
    "降额",
    "通信",
    "通讯",
    "离线",
    "采集器",
    "RS485",
    "网络",
    "MPPT",
    "发电低",
    "功率低",
    "电流低",
    "遮挡",
    "短路",
]


FAULT_KEYWORDS: dict[str, list[str]] = {
    "low_insulation": ["绝缘", "绝缘阻抗", "对地绝缘", "绝缘低", "漏电", "接地", "insulation", "insulation resistance"],
    "low_insulation_resistance": ["绝缘", "绝缘阻抗", "对地绝缘", "绝缘低", "漏电", "接地", "insulation", "insulation resistance"],
    "overtemperature": ["过温", "温度高", "散热", "风扇", "通风", "降额", "overtemperature", "temperature", "fan", "derating"],
    "over_temperature": ["过温", "温度高", "散热", "风扇", "通风", "降额", "overtemperature", "temperature", "fan", "derating"],
    "fan_fault": ["风扇", "散热", "过温", "通风", "降额", "fan", "cooling", "ventilation"],
    "communication_fault": ["通信", "通讯", "离线", "采集器", "FusionSolar", "RS485", "网络", "communication", "offline", "datalogger"],
    "communication_interruption": ["通信", "通讯", "离线", "采集器", "FusionSolar", "RS485", "网络", "communication", "offline", "datalogger"],
    "device_offline": ["离线", "通信", "通讯", "网络", "采集器", "FusionSolar", "offline", "communication", "network"],
    "mppt_low_power": ["MPPT", "组串", "发电低", "功率低", "电流低", "遮挡", "组件", "string", "power", "current", "shading"],
    "mppt_abnormal": ["MPPT", "组串", "发电低", "功率低", "电流低", "遮挡", "组件", "string", "power", "current", "shading"],
    "low_power_generation": ["MPPT", "组串", "发电低", "功率低", "电流低", "遮挡", "组件", "降额", "generation", "power", "derating"],
    "grid_fault": ["电网", "交流", "并网", "电压", "频率", "电网异常", "grid", "AC", "voltage", "frequency"],
    "grid_connection_fault": ["电网", "交流", "并网", "电压", "频率", "电网异常", "grid", "AC", "voltage", "frequency"],
    "ac_overvoltage": ["交流", "过压", "电网", "电压", "并网", "AC", "overvoltage", "grid", "voltage"],
    "ac_undervoltage": ["交流", "欠压", "电网", "电压", "并网", "AC", "undervoltage", "grid", "voltage"],
    "dc_abnormal": ["直流", "组串", "组件", "电流", "电压", "异常", "DC", "string", "current", "voltage"],
    "alarm_code_query": ["告警", "告警码", "故障代码", "处理建议", "alarm", "alarm code", "troubleshooting"],
}


MANUFACTURER_KEYWORDS = {
    "huawei": ["华为", "SUN2000", "FusionSolar"],
    "sungrow": ["阳光", "阳光电源", "Sungrow", "SG"],
}


PRODUCT_SERIES_KEYWORDS = {
    "SUN2000": ["SUN2000", "华为", "逆变器"],
    "FusionSolar": ["FusionSolar", "华为", "监控", "通信"],
    "SG": ["SG", "阳光", "阳光电源", "Sungrow"],
}


@dataclass
class QueryExpansionResult:
    normalized_query: str
    keywords: list[str] = field(default_factory=list)


class QueryExpansionService:
    def expand(self, payload: RetrievalQueryRequest) -> QueryExpansionResult:
        normalized_query = self.normalize_question(payload.normalized_question)
        keywords: list[str] = [normalized_query]

        keywords.extend(self._extract_text_terms(normalized_query))
        if payload.alarm_code:
            keywords.append(payload.alarm_code)
        if payload.fault_type:
            keywords.append(payload.fault_type)
            keywords.extend(FAULT_KEYWORDS.get(payload.fault_type, []))
        if payload.manufacturer:
            keywords.extend(MANUFACTURER_KEYWORDS.get(payload.manufacturer, []))
        if payload.product_series:
            keywords.extend(PRODUCT_SERIES_KEYWORDS.get(payload.product_series, []))
        for term in DOMAIN_TERMS:
            if term.lower() in normalized_query.lower():
                keywords.append(term)

        return QueryExpansionResult(
            normalized_query=normalized_query,
            keywords=self._unique_keywords(keywords),
        )

    @staticmethod
    def normalize_question(question: str) -> str:
        return re.sub(r"\s+", " ", question.strip())

    def _extract_text_terms(self, text: str) -> list[str]:
        terms: list[str] = []
        terms.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-./]*", text))
        chinese_blocks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        for block in chinese_blocks:
            terms.append(block)
            terms.extend(self._chinese_ngrams(block))
        return terms

    @staticmethod
    def _chinese_ngrams(text: str) -> list[str]:
        terms: list[str] = []
        max_terms = 40
        for size in (4, 3, 2):
            for start in range(0, max(0, len(text) - size + 1)):
                term = text[start : start + size]
                if term not in terms:
                    terms.append(term)
                if len(terms) >= max_terms:
                    return terms
        return terms

    @staticmethod
    def _unique_keywords(keywords: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for keyword in keywords:
            normalized = keyword.strip()
            if len(normalized) < 2:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
            if len(unique) >= 80:
                break
        return unique
