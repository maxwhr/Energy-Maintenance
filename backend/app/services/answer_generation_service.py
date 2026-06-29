from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.retrieval import RetrievedChunk, RetrievalQueryRequest


GENERIC_SAFETY_NOTES = [
    "检修前确认逆变器已停机或处于厂家手册要求的安全状态。",
    "涉及直流侧、交流侧和电网侧操作时，应由具备资质的人员执行。",
    "现场处理应以设备厂家手册、电站安全规程和挂牌上锁要求为准。",
]


FAULT_SAFETY_NOTES = {
    "low_insulation": ["绝缘相关故障排查前应确认直流侧已安全隔离，严禁带电插拔组串接头。"],
    "low_insulation_resistance": ["绝缘相关故障排查前应确认直流侧已安全隔离，严禁带电插拔组串接头。"],
    "overtemperature": ["过温相关排查应避免直接接触高温部件，待设备降温后再检查风道和风扇。"],
    "over_temperature": ["过温相关排查应避免直接接触高温部件，待设备降温后再检查风道和风扇。"],
    "communication_fault": ["通信排查不得随意更改站内网络地址、采集器配置或监控平台参数。"],
    "communication_interruption": ["通信排查不得随意更改站内网络地址、采集器配置或监控平台参数。"],
    "mppt_low_power": ["MPPT 与组串排查前应确认组串电压、电流在安全测量范围内。"],
    "mppt_abnormal": ["MPPT 与组串排查前应确认组串电压、电流在安全测量范围内。"],
    "grid_fault": ["电网侧异常排查应遵守并网点操作票和电气安全距离要求。"],
    "grid_connection_fault": ["电网侧异常排查应遵守并网点操作票和电气安全距离要求。"],
}


@dataclass
class GeneratedAnswer:
    answer: str
    suggested_steps: list[str] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    confidence: float = 0.1


class AnswerGenerationService:
    def generate(
        self,
        *,
        payload: RetrievalQueryRequest,
        retrieved_chunks: list[RetrievedChunk],
        keywords: list[str],
        kg_context: dict | None = None,
    ) -> GeneratedAnswer:
        safety_notes = self._build_safety_notes(payload)
        if not retrieved_chunks:
            kg_note = self._kg_answer_note(kg_context)
            answer = (
                "当前知识库未检索到足够可靠的依据，不能基于不存在的资料生成具体检修结论。"
                "建议补充华为或阳光电源光伏逆变器设备手册、告警代码说明、检修规程或故障案例后再查询。"
            )
            if kg_note:
                answer = f"{answer}\n\n{kg_note}"
            return GeneratedAnswer(
                answer=answer,
                suggested_steps=[],
                safety_notes=safety_notes,
                confidence=0.18 if kg_note else 0.1,
            )

        directions = self._extract_directions(retrieved_chunks[:5], keywords)
        if not directions:
            directions = [
                "核对告警代码、设备状态和发生时间，确认故障现象是否持续存在。",
                "按检索到的厂家资料逐项检查直流侧、交流侧、通信链路和散热条件。",
                "处理后复核告警是否消除，并将现场处理过程归档。",
            ]

        direction_text = "\n".join(f"{index}. {item}" for index, item in enumerate(directions[:5], start=1))
        answer = (
            "根据当前知识库检索结果，建议按以下方向排查：\n"
            f"{direction_text}\n"
            "以上结论来源于知识库片段，现场作业仍需遵守设备厂家手册和电站安全规范。"
        )
        kg_note = self._kg_answer_note(kg_context)
        if kg_note:
            answer = f"{answer}\n\n{kg_note}"

        return GeneratedAnswer(
            answer=answer,
            suggested_steps=self._build_suggested_steps(payload, directions, kg_context=kg_context),
            safety_notes=safety_notes,
            confidence=self._calculate_confidence(retrieved_chunks),
        )

    def _extract_directions(self, chunks: list[RetrievedChunk], keywords: list[str]) -> list[str]:
        directions: list[str] = []
        keyword_set = [keyword.lower() for keyword in keywords[:30]]
        for chunk in chunks:
            sentences = self._split_sentences(chunk.content)
            matched = [
                sentence
                for sentence in sentences
                if any(keyword.lower() in sentence.lower() for keyword in keyword_set)
            ]
            source_sentences = matched or sentences[:2]
            for sentence in source_sentences:
                cleaned = self._compact_sentence(sentence)
                if not cleaned or cleaned in directions:
                    continue
                directions.append(cleaned)
                if len(directions) >= 5:
                    return directions
        return directions

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"[。！？!?；;\n]+", text)
        return [part.strip(" -\t\r") for part in parts if part.strip(" -\t\r")]

    @staticmethod
    def _compact_sentence(sentence: str) -> str:
        compact = re.sub(r"\s+", " ", sentence).strip()
        if len(compact) > 110:
            compact = f"{compact[:110]}..."
        return compact

    def _build_suggested_steps(
        self,
        payload: RetrievalQueryRequest,
        directions: list[str],
        *,
        kg_context: dict | None = None,
    ) -> list[str]:
        steps = [
            "安全确认：确认逆变器、电网侧和直流侧满足现场检修安全条件。",
            "故障现象核对：记录告警代码、发生时间、设备状态和是否复发。",
            "设备状态检查：检查运行状态、通信状态、散热状态和组串输入。",
            "关键部件排查：结合检索片段逐项核对可能原因。",
            "处理措施确认：按厂家手册执行复位、清洁、紧固、隔离或更换等操作。",
            "复检与记录归档：确认告警解除并保存 QA trace、现场照片和检修记录。",
        ]
        if payload.fault_type in {"low_insulation", "low_insulation_resistance"}:
            steps.insert(3, "绝缘专项检查：分段隔离组串、电缆和接地回路，确认绝缘阻抗变化。")
        if payload.fault_type in {"overtemperature", "over_temperature", "fan_fault"}:
            steps.insert(3, "散热专项检查：检查风扇、风道、滤网、环境温度和降额记录。")
        if payload.fault_type in {"communication_fault", "communication_interruption", "device_offline"}:
            steps.insert(3, "通信专项检查：检查采集器、RS485、网络链路和 FusionSolar 侧状态。")
        if payload.fault_type in {"mppt_low_power", "mppt_abnormal", "low_power_generation"}:
            steps.insert(3, "组串专项检查：核对组串电压、电流、遮挡、污染和接线一致性。")
        if directions:
            steps.append(f"重点参考：{directions[0]}")
        for item in (kg_context or {}).get("inspection_items", [])[:2]:
            name = item.get("display_name") or item.get("canonical_name")
            if name:
                steps.append(f"图谱关联排查：重点核对{name}。")
        return steps

    @staticmethod
    def _kg_answer_note(kg_context: dict | None) -> str | None:
        if not kg_context:
            return None
        summary = kg_context.get("summary") or {}
        if not summary.get("matched_node_count"):
            return None
        causes = [
            item.get("display_name") or item.get("canonical_name")
            for item in kg_context.get("related_causes", [])[:3]
        ]
        actions = [
            item.get("display_name") or item.get("canonical_name")
            for item in kg_context.get("recommended_actions", [])[:3]
        ]
        risks = [
            item.get("display_name") or item.get("canonical_name")
            for item in kg_context.get("safety_risks", [])[:3]
        ]
        parts = ["图谱增强提示：已命中 active 知识图谱节点与可追溯 evidence。"]
        if causes:
            parts.append(f"关联可能原因：{'、'.join(item for item in causes if item)}。")
        if actions:
            parts.append(f"关联处理措施：{'、'.join(item for item in actions if item)}。")
        if risks:
            parts.append(f"关联安全风险：{'、'.join(item for item in risks if item)}。")
        return "".join(parts)

    @staticmethod
    def _calculate_confidence(chunks: list[RetrievedChunk]) -> float:
        if not chunks:
            return 0.1
        top_score = chunks[0].score
        if len(chunks) == 1:
            return min(0.55, 0.35 + min(top_score, 20) / 100)
        average_score = sum(chunk.score for chunk in chunks[:5]) / min(len(chunks), 5)
        confidence = 0.55 + min(average_score, 40) / 140 + min(len(chunks), 5) * 0.02
        return round(min(confidence, 0.85), 2)

    @staticmethod
    def _build_safety_notes(payload: RetrievalQueryRequest) -> list[str]:
        notes = list(GENERIC_SAFETY_NOTES)
        if payload.fault_type:
            notes.extend(FAULT_SAFETY_NOTES.get(payload.fault_type, []))
        return list(dict.fromkeys(notes))
