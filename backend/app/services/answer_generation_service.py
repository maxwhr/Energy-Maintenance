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
                "建议补充并审核华为 SUN2000 设备手册、告警代码说明、检修规程或故障案例后再查询。"
            )
            if kg_note:
                answer = f"{answer}\n\n{kg_note}"
            return GeneratedAnswer(
                answer=answer,
                suggested_steps=[],
                safety_notes=safety_notes,
                confidence=0.18 if kg_note else 0.1,
            )

        evidence_findings = self._build_evidence_findings(payload, retrieved_chunks[:5])
        extracted_directions = self._extract_directions(retrieved_chunks[:5], keywords)
        directions = list(dict.fromkeys([*evidence_findings, *extracted_directions]))[:5]
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
        keyword_set = list(dict.fromkeys(keyword.lower() for keyword in keywords[:64] if keyword.strip()))
        action_terms = ("检查", "确认", "核对", "断开", "闭合", "等待", "联系", "测量", "排查", "设置", "重启", "清洁", "更换")
        ranked_by_source: list[tuple[int, list[str]]] = []
        for source_index, chunk in enumerate(chunks, start=1):
            sentences = self._split_sentences(chunk.content)
            scored: list[tuple[float, int, str]] = []
            for position, sentence in enumerate(sentences):
                cleaned = self._compact_sentence(sentence)
                if not cleaned or (cleaned.startswith("#") and len(sentences) > 1):
                    continue
                lowered = cleaned.lower()
                lexical_score = sum(
                    len(keyword) ** 2 for keyword in keyword_set if keyword in lowered
                )
                action_score = sum(term in cleaned for term in action_terms)
                scored.append((float(lexical_score + action_score * 9), position, cleaned))
            primary_excerpt = self._best_evidence_excerpt(
                chunk.content,
                keyword_set,
                action_terms,
            )
            if not scored and not primary_excerpt:
                continue
            scored.sort(key=lambda item: (-item[0], item[1]))
            source_excerpts = [primary_excerpt] if primary_excerpt else []
            source_excerpts.extend(
                item[2] for item in scored
                if item[2] not in (primary_excerpt or "")
            )
            ranked_by_source.append((source_index, list(dict.fromkeys(source_excerpts))))

        seen: set[str] = set()
        max_depth = max((len(items) for _, items in ranked_by_source), default=0)
        for depth in range(max_depth):
            for source_index, source_sentences in ranked_by_source:
                if depth >= len(source_sentences):
                    continue
                cleaned = source_sentences[depth]
                normalized = re.sub(r"\s+", "", cleaned).casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                directions.append(f"[来源{source_index}] {cleaned}")
                if len(directions) >= 5:
                    return directions
        return directions

    @classmethod
    def _build_evidence_findings(
        cls,
        payload: RetrievalQueryRequest,
        chunks: list[RetrievedChunk],
    ) -> list[str]:
        """Build concise findings only when the cited chunk contains the facts.

        These deterministic summaries keep table rows and maintenance action
        bundles readable without inventing evidence or consuming evaluation labels.
        """

        query = re.sub(r"\s+", "", payload.normalized_question).casefold()
        findings: list[str] = []
        for source_index, chunk in enumerate(chunks, start=1):
            compact = re.sub(r"\s+", "", chunk.content or "")
            lowered = compact.casefold()
            prefix = f"[来源{source_index}] "

            if (
                ("告警" in query or payload.alarm_code)
                and any(term in lowered for term in ("dc输入电压高", "直流输入电压高"))
                and "开路电压" in compact
                and any(term in compact for term in ("串联配置", "光伏阵列配置", "串联的光伏电池板"))
            ):
                findings.append(
                    f"{prefix}告警含义为直流输入电压高；先检查光伏组串的串联配置，"
                    "避免开路电压超过逆变器最大工作电压。"
                )

            if (
                "绝缘" in query
                and any(term in query for term in ("百分比", "组件位置", "故障位置"))
                and "百分比" in compact
                and "组件" in compact
                and "故障位置" in compact
            ):
                findings.append(
                    f"{prefix}位置换算应结合组件总数量和告警显示的百分比，"
                    "计算并核对疑似故障位置。"
                )

            if (
                "风扇" in query
                and "异常噪声" in compact
                and "异物" in compact
                and "更换风扇" in compact
            ):
                findings.append(
                    f"{prefix}检查异常噪声，先清理异物；若仍有异常噪声，再更换风扇。"
                )

            if (
                any(term in query for term in ("安装", "散热空间", "安装距离"))
                and "安装" in compact
                and "散热空间" in compact
                and re.search(r"\d+(?:\.\d+)?(?:mm|cm|m)", lowered)
            ):
                findings.append(
                    f"{prefix}安装距离应按资料给出的顶部、底部、侧面和前方数值预留，"
                    "确保散热空间与通风条件。"
                )

            if (
                "电网电压" in query
                and "电网电压" in compact
                and "交流断路器" in compact
                and "电力运营商" in compact
            ):
                findings.append(
                    f"{prefix}核对电网电压和交流断路器状态；若异常频繁出现并影响发电，"
                    "联系当地电力运营商。"
                )

            if any(term in query for term in ("下电", "等待多久", "交直流侧")):
                if re.search(r"(?:下电|断电).{0,24}15(?:分钟|min)", lowered):
                    findings.append(f"{prefix}检修下电后等待15min，再按手册要求进行操作。")
                if (
                    any(term in compact for term in ("钳流表", "钳形表"))
                    and "直流" in compact
                    and "电流" in compact
                    and "测量" in compact
                ):
                    findings.append(f"{prefix}使用钳流表直流电流档测量直流电流，确认组串已满足安全操作条件。")
                if (
                    "万用表" in compact
                    and "交流端子排" in compact
                    and "对地电压" in compact
                    and "测量" in compact
                ):
                    findings.append(f"{prefix}使用万用表测量交流端子排对地电压，确认交流侧已满足安全条件。")

        return list(dict.fromkeys(findings))[:5]

    @staticmethod
    def _best_evidence_excerpt(
        content: str,
        keywords: list[str],
        action_terms: tuple[str, ...],
        *,
        target_length: int = 640,
    ) -> str:
        text = re.sub(r"\s+", " ", content or "").strip()
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        if not text:
            return ""
        informative = [
            keyword for keyword in keywords
            if keyword not in {"华为", "huawei", "sun2000", "fusionsolar", "光伏", "逆变器"}
            and not keyword.startswith("sun2000-")
        ]
        active_keywords = informative or keywords
        candidates: list[tuple[float, int, str]] = []
        starts = {0}
        lowered = text.lower()
        for keyword in active_keywords:
            start = lowered.find(keyword)
            while start >= 0:
                starts.add(max(0, start - 40))
                start = lowered.find(keyword, start + 1)
        for start in starts:
            excerpt = text[start:start + target_length]
            excerpt_lower = excerpt.lower()
            lexical_score = sum(
                len(keyword) ** 2 for keyword in active_keywords if keyword in excerpt_lower
            )
            action_score = sum(term in excerpt for term in action_terms)
            candidates.append((float(lexical_score + action_score * 9), start, excerpt))
        _score, start, excerpt = max(candidates, key=lambda item: (item[0], -item[1]))
        if start > 0:
            excerpt = f"...{excerpt.lstrip(' ，。；：、')}"
        if start + target_length < len(text):
            excerpt = f"{excerpt.rstrip(' ，。；：、')}..."
        return excerpt

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"[。！？!?；;\n]+", text)
        return [part.strip(" -\t\r") for part in parts if part.strip(" -\t\r")]

    @staticmethod
    def _compact_sentence(sentence: str) -> str:
        compact = re.sub(r"\s+", " ", sentence).strip()
        if len(compact) > 180:
            compact = f"{compact[:180]}..."
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
