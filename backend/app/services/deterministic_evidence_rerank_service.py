from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.query_understanding import QueryUnderstandingResult
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.rrf_fusion_service import QueryAwareCandidate


@dataclass(slots=True)
class DeterministicEvidenceRerankResult:
    candidates: list[QueryAwareCandidate]
    diagnostics: dict[str, Any]


class DeterministicEvidenceRerankService:
    """V2 graded deterministic reranker; benchmark grades are never inputs."""

    VERSION = "task27a_huawei_keyword_rerank_v5"
    MODEL_PATTERN = re.compile(r"(?:SUN2000|LUNA2000|SmartLogger|SG)[A-Z0-9()/_.-]*", re.I)
    ALARM_PATTERN = re.compile(r"(?:告警|故障(?:码)?)[：:\s-]*([A-Z]{0,4}\d{3,6})", re.I)
    SUPPORT_TERMS = {
        "CAUSE": (
            "原因", "导致", "可能由于", "由于", "引起", "用于", "为了", "目的",
            "使能", "找到", "最大功率点", "全局扫描",
        ),
        "ACTION": ("处理", "排查", "检查", "更换", "重启", "确认"),
        "PROCEDURE": ("步骤", "操作", "流程", "顺序", "首先", "然后"),
        "SAFETY": ("安全", "危险", "触电", "断电", "验电", "防护"),
        "ALARM_MEANING": ("告警", "故障码", "含义", "影响"),
        "PREREQUISITE": ("前提", "条件", "准备", "操作前", "开始前"),
        "VERIFICATION": (
            "验证", "确认", "确定", "恢复", "是否正常", "完成后", "测量", "万用表",
            "钳形表", "电压", "电流", "验电", "不大于", "小于",
        ),
        "CONFIGURATION": ("配置", "设置", "参数", "地址", "波特率", "协议"),
        "COMMUNICATION": ("通信", "断链", "RS485", "WiFi", "WLAN", "网络", "离线", "掉线"),
        "TROUBLESHOOTING": ("排查", "检查", "定位", "处理", "故障", "告警", "原因"),
        "DIAGNOSIS": ("诊断", "原因", "故障", "异常", "检查", "排查"),
        "COMPONENT": ("部件", "组件", "模块", "线缆", "端子", "风扇", "开关"),
        "GENERAL_INFORMATION": (),
    }
    WEIGHTS = {
        "normalized_rrf_score": 0.31,
        "query_lexical_support": 0.12,
        "direct_answer_score": 0.20,
        "requested_information_coverage": 0.08,
        "intent_match": 0.06,
        "entity_match": 0.07,
        "condition_match": 0.02,
        "evidence_specificity": 0.04,
        "source_grounding": 0.03,
        "citation_quality": 0.03,
        "channel_consensus": 0.02,
        "semantic_support": 0.01,
        "keyword_support": 0.005,
        "vector_support": 0.005,
    }
    DUPLICATE_PENALTY = 0.06
    ENTITY_CONFLICT_PENALTY = 0.18
    EVIDENCE_CONFLICT_PENALTY = 0.22
    BACKGROUND_ONLY_PENALTY = 0.12
    GENERALITY_PENALTY_WEIGHT = 0.18
    PHRASE_PROXIMITY_BONUS_WEIGHT = 0.18
    DOCUMENT_PURPOSE_BONUS_WEIGHT = 0.12
    DIRECT_LEVEL_BONUS = {
        "DIRECT_ANSWER": 0.12,
        "DIRECT_SUPPORT": 0.04,
        "NON_SUPPORTING": 0.0,
        "BACKGROUND_ONLY": -0.08,
    }
    QUERY_BOILERPLATE_TERMS = {
        "什么", "怎么", "怎样", "如何", "为何", "为什么", "是否", "能否", "哪里",
        "多久", "哪些", "需要", "应该", "可以", "进行", "时候", "场景", "问题",
        "华为", "huawei", "fusionsolar", "sun2000", "光伏", "逆变器", "设备",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.weights = dict(self.WEIGHTS)
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"deterministic rerank weights must sum to 1.0, got {total:.8f}")

    def rerank(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
        citation_status: dict[str, bool] | None = None,
    ) -> DeterministicEvidenceRerankResult:
        original = list(candidates)
        original_ids = [item.candidate_id for item in original]
        if not original:
            return DeterministicEvidenceRerankResult([], self._diagnostics([], [], {}, True))
        rrf_values = [max(0.0, float(item.rrf_score)) for item in original]
        keyword_values = [self._channel_score(item, ("KEYWORD",)) for item in original]
        vector_values = [self._channel_score(item, ("RAW_VECTOR", "VECTOR")) for item in original]
        semantic_values = [self._semantic_score(item) for item in original]
        query_terms = QuerySignalExtractionService.retrieval_terms(
            understanding.original_query or understanding.normalized_query,
            limit=96,
        )
        model_terms = {
            self._normalize_model_identifier(value).casefold()
            for value in understanding.device_models
            if value
        }
        query_terms = [
            term for term in query_terms
            if self._normalize_model_identifier(term).casefold() not in model_terms
        ]
        lexical_values = [
            self.query_lexical_support(
                query_terms,
                f"{item.section_title or ''} {item.content}",
            )
            for item in original
        ]
        candidate_texts = [f"{item.section_title or ''} {item.content}" for item in original]
        phrase_sensitive_information = {
            "CAUSE", "CONFIGURATION", "SAFETY", "VERIFICATION", "PREREQUISITE",
        }
        query_text = self._compact_match_text(
            understanding.original_query or understanding.normalized_query
        )
        calculation_procedure = (
            "PROCEDURE" in understanding.requested_information
            and any(term in query_text for term in ("计算", "换算", "百分比", "数量", "位置"))
        )
        phrase_feature_enabled = bool(
            phrase_sensitive_information.intersection(understanding.requested_information)
        ) or calculation_procedure
        phrase_profiles = (
            self.phrase_proximity_profiles(query_terms, candidate_texts)
            if phrase_feature_enabled
            else [
                {"score": 0.0, "anchor_terms": [], "matched_terms": []}
                for _ in candidate_texts
            ]
        )
        specific_models = {
            self._normalize_model_identifier(value)
            for value in understanding.device_models
            if self._normalize_model_identifier(value) != "SUN2000"
        }
        content_seen: set[str] = set()
        breakdown: dict[str, dict[str, Any]] = {}
        protection: dict[str, int] = {}
        for index, item in enumerate(original):
            citation_quality = self._citation_quality(item, citation_status)
            requested_support = self.requested_information_support(
                f"{item.section_title or ''} {item.content}", understanding.requested_information
            )
            if calculation_procedure and self._calculation_evidence_score(
                query_text,
                self._compact_match_text(f"{item.section_title or ''} {item.content}"),
            ) >= 0.75:
                requested_support.add("PROCEDURE")
            coverage = len(requested_support) / max(1, len(set(understanding.requested_information)))
            generality = self.generality_penalty(item, coverage)
            specificity = max(0.0, 1.0 - generality)
            intent_match = self._intent_match(
                item,
                understanding,
                query_support=lexical_values[index],
            )
            document_purpose_match = self._document_purpose_match(item, understanding)
            entity_match = self._entity_match(item, understanding)
            condition_match = self._term_overlap(understanding.conditions, item.content) if understanding.conditions else 1.0
            query_lexical_support = self._normalize(lexical_values[index], lexical_values)
            phrase_profile = phrase_profiles[index]
            phrase_proximity_support = float(phrase_profile["score"])
            direct_score = self.direct_answer_score(
                coverage=coverage,
                intent_match=intent_match,
                entity_match=entity_match,
                specificity=specificity,
                citation_quality=citation_quality,
                query_support=query_lexical_support,
            )
            direct_level = self.direct_answer_level(direct_score, coverage, generality)
            item.requested_information_support = set(requested_support)
            item.requested_information_coverage = round(coverage, 6)
            item.direct_answer_score = round(direct_score, 6)
            item.direct_answer_level = direct_level
            item.generality_penalty = round(generality, 6)
            values = {
                "normalized_rrf_score": self._normalize(rrf_values[index], rrf_values),
                "query_lexical_support": query_lexical_support,
                "direct_answer_score": direct_score,
                "requested_information_coverage": coverage,
                "intent_match": intent_match,
                "entity_match": entity_match,
                "condition_match": condition_match,
                "evidence_specificity": specificity,
                "source_grounding": self._source_quality(item),
                "citation_quality": citation_quality,
                "channel_consensus": min(1.0, len(item.source_channels) / 3.0),
                "semantic_support": self._normalize(semantic_values[index], semantic_values),
                "keyword_support": self._normalize(keyword_values[index], keyword_values),
                "vector_support": self._normalize(vector_values[index], vector_values),
            }
            conflict_penalty, conflict_reasons = self._conflict_penalty(item, understanding)
            content_hash = self._content_hash(item.content)
            duplicate_penalty = self.DUPLICATE_PENALTY if content_hash in content_seen else 0.0
            content_seen.add(content_hash)
            background_penalty = self.BACKGROUND_ONLY_PENALTY if direct_level == "BACKGROUND_ONLY" else 0.0
            positive = sum(values[key] * weight for key, weight in self.weights.items())
            total_penalty = conflict_penalty + duplicate_penalty + background_penalty + generality * self.GENERALITY_PENALTY_WEIGHT
            final_score = max(
                0.0,
                min(
                    1.0,
                    positive
                    + phrase_proximity_support * self.PHRASE_PROXIMITY_BONUS_WEIGHT
                    + document_purpose_match * self.DOCUMENT_PURPOSE_BONUS_WEIGHT
                    - total_penalty,
                ),
            )
            item.rerank_score = round(final_score, 8)
            item.final_score = item.rerank_score
            protection[item.candidate_id] = int(
                entity_match >= 1.0 and coverage > 0 and query_lexical_support >= 0.45
                and citation_quality >= 1.0
                and conflict_penalty == 0 and bool(
                    (specific_models and item.exact_model_match)
                    or ((understanding.alarm_codes or understanding.alarm_names) and item.exact_alarm_match)
                )
            )
            protection_reason = ["EXACT_ENTITY_VALID_CITATION_PROTECTED"] if protection[item.candidate_id] else []
            breakdown[item.candidate_id] = {
                "candidate_id": item.candidate_id,
                "evidence_identity": item.evidence_identity,
                "direct_answer_level": direct_level,
                "supported_requested_information": sorted(requested_support),
                **{key: round(value, 6) for key, value in values.items()},
                "exact_model_match": 1.0 if understanding.device_models and item.exact_model_match else 0.0,
                "exact_alarm_match": 1.0 if (understanding.alarm_codes or understanding.alarm_names) and item.exact_alarm_match else 0.0,
                "generality_penalty": round(generality, 6),
                "background_only_penalty": round(background_penalty, 6),
                "entity_conflict_penalty": round(conflict_penalty, 6),
                "conflict_penalty": round(conflict_penalty, 6),
                "duplicate_penalty": round(duplicate_penalty, 6),
                "phrase_proximity_support": round(phrase_proximity_support, 6),
                "phrase_anchor_terms": list(phrase_profile["anchor_terms"]),
                "matched_phrase_anchor_terms": list(phrase_profile["matched_terms"]),
                "document_purpose_match": round(document_purpose_match, 6),
                "final_score": item.final_score,
                "reason_codes": [direct_level, *protection_reason, *conflict_reasons],
            }
        original_position = {candidate_id: index for index, candidate_id in enumerate(original_ids)}
        ranked = sorted(
            original,
            key=lambda item: (
                -protection[item.candidate_id],
                -round(item.final_score + self.DIRECT_LEVEL_BONUS.get(item.direct_answer_level, 0.0), 8),
                -round(item.direct_answer_score, 8),
                -round(float(breakdown[item.candidate_id].get("entity_match") or 0.0), 8),
                -round(item.requested_information_coverage, 8),
                original_position[item.candidate_id],
                item.evidence_equivalence_key or item.evidence_identity or item.candidate_id,
            ),
        )
        ranked_ids = [item.candidate_id for item in ranked]
        if set(ranked_ids) != set(original_ids) or len(ranked_ids) != len(original_ids):
            raise RuntimeError("deterministic rerank candidate boundary violation")
        source_snapshot = {
            item.candidate_id: (set(item.source_channels), list(item.source_chunk_ids), dict(item.source_locator))
            for item in original
        }
        source_unchanged = all(
            source_snapshot[item.candidate_id] == (
                set(item.source_channels), list(item.source_chunk_ids), dict(item.source_locator)
            ) for item in ranked
        )
        return DeterministicEvidenceRerankResult(
            ranked, self._diagnostics(original_ids, ranked_ids, breakdown, source_unchanged)
        )

    @classmethod
    def requested_information_support(cls, text: str, requested: list[str]) -> set[str]:
        lowered = (text or "").lower()
        output: set[str] = set()
        for name in set(requested):
            terms = cls.SUPPORT_TERMS.get(name, ())
            if name == "GENERAL_INFORMATION" or (
                terms and any(term.lower() in lowered for term in terms)
            ):
                output.add(name)
        return output

    @staticmethod
    def query_lexical_support(terms: list[str], text: str) -> float:
        """Measure direct Chinese/identifier support without whitespace tokenization.

        Longer query fragments carry more weight so a candidate containing the
        user's concrete phrase outranks a generic chunk that only shares common
        two-character words.
        """

        compact_text = re.sub(r"\s+", "", (text or "").casefold())
        weighted_terms: dict[str, float] = {}
        for term in terms:
            compact_term = re.sub(r"\s+", "", term.casefold()).strip()
            if len(compact_term) < 2:
                continue
            weighted_terms.setdefault(compact_term, float(len(compact_term) ** 2))
        total_weight = sum(weighted_terms.values())
        if not compact_text or total_weight <= 0:
            return 0.0
        matched_weight = sum(
            weight for term, weight in weighted_terms.items() if term in compact_text
        )
        return max(0.0, min(1.0, matched_weight / total_weight))

    @classmethod
    def phrase_proximity_profiles(
        cls,
        terms: list[str],
        texts: list[str],
        *,
        max_anchors: int = 8,
    ) -> list[dict[str, Any]]:
        """Score rare query phrases and their local co-occurrence in each candidate.

        The feature is derived only from the live query and candidate set. It does
        not consume benchmark labels, document IDs, chunk IDs, or expected ranks.
        This matters for Chinese maintenance questions where whitespace tokenization
        loses identifiers such as ``RS485-2`` and compound phrases such as
        ``通信断链保护时间``.
        """

        compact_texts = [cls._compact_match_text(text) for text in texts]
        document_count = len(compact_texts)
        if not document_count:
            return []

        weighted_terms: list[tuple[float, str]] = []
        for raw_term in dict.fromkeys(terms):
            term = cls._compact_match_text(raw_term)
            if len(term) < 2 or term in cls.QUERY_BOILERPLATE_TERMS:
                continue
            if all(part in cls.QUERY_BOILERPLATE_TERMS for part in re.findall(r"[a-z0-9_.-]+|[\u4e00-\u9fff]+", term)):
                continue
            frequency = sum(term in text for text in compact_texts)
            if frequency == 0:
                continue
            inverse_frequency = 1.0 + math.log((document_count + 1) / (frequency + 1))
            identifier_bonus = 1.35 if re.search(r"[a-z].*\d|\d.*[a-z]", term) else 1.0
            weighted_terms.append((len(term) ** 2 * inverse_frequency * identifier_bonus, term))

        anchors: list[tuple[float, str]] = []
        for weight, term in sorted(weighted_terms, key=lambda item: (-item[0], -len(item[1]), item[1])):
            if any(term in selected or selected in term for _, selected in anchors):
                continue
            anchors.append((weight, term))
            if len(anchors) >= max_anchors:
                break

        total_weight = sum(weight for weight, _ in anchors)
        if len(anchors) < 2 or total_weight <= 0:
            return [
                {"score": 0.0, "anchor_terms": [], "matched_terms": []}
                for _ in compact_texts
            ]

        anchor_terms = [term for _, term in anchors]
        profiles: list[dict[str, Any]] = []
        for text in compact_texts:
            matches = [
                (weight, term, text.find(term))
                for weight, term in anchors
                if term in text
            ]
            coverage = sum(weight for weight, _, _ in matches) / total_weight
            proximity = 0.0
            if len(matches) == 1:
                proximity = 0.5
            elif len(matches) > 1:
                starts = [position for _, _, position in matches]
                ends = [position + len(term) for _, term, position in matches]
                span = max(ends) - min(starts)
                proximity = max(0.0, min(1.0, 1.0 - max(0, span - 48) / 240))
            score = min(1.0, coverage * 0.85 + proximity * 0.15)
            profiles.append({
                "score": round(score, 8),
                "anchor_terms": anchor_terms,
                "matched_terms": [term for _, term, _ in matches],
            })
        return profiles

    @staticmethod
    def _compact_match_text(value: str) -> str:
        return re.sub(r"\s+", "", (value or "").casefold()).strip("，。；：、！？?()（）[]【】\"'")

    @staticmethod
    def direct_answer_score(
        *,
        coverage: float,
        intent_match: float,
        entity_match: float,
        specificity: float,
        citation_quality: float,
        query_support: float = 1.0,
    ) -> float:
        return max(
            0.0,
            min(
                1.0,
                0.20 * query_support
                + 0.28 * coverage
                + 0.17 * intent_match
                + 0.10 * entity_match
                + 0.15 * specificity
                + 0.10 * citation_quality,
            ),
        )

    @staticmethod
    def direct_answer_level(score: float, coverage: float, generality: float) -> str:
        if coverage >= 0.75 and score >= 0.68 and generality < 0.5:
            return "DIRECT_ANSWER"
        if coverage > 0 and score >= 0.42:
            return "DIRECT_SUPPORT"
        if generality >= 0.5:
            return "BACKGROUND_ONLY"
        return "NON_SUPPORTING"

    @staticmethod
    def generality_penalty(item: QueryAwareCandidate, coverage: float) -> float:
        text = f"{item.section_title or ''} {item.content or ''}".strip()
        locator = item.source_locator or {}
        penalty = 0.0
        if "FULL_SECTION" in item.source_query_types or str(locator.get("anchor_type") or "").upper() == "FULL_SECTION":
            penalty += 0.55
        if len(item.content or "") > 1800:
            penalty += 0.20
        if len(item.content or "") < 80 and item.section_title:
            penalty += 0.25
        if coverage == 0:
            penalty += 0.25
        if any(term in text for term in ("目录", "产品介绍", "概述", "章节")):
            penalty += 0.20
        return min(1.0, penalty)

    def _diagnostics(self, original_ids, ranked_ids, breakdown, source_unchanged):
        return {
            "executed": True,
            "weights_version": self.VERSION,
            "weights": dict(self.weights),
            "weights_sum": round(sum(self.weights.values()), 8),
            "candidates_in": len(original_ids),
            "candidates_out": len(ranked_ids),
            "order_changed": original_ids != ranked_ids,
            "candidate_additions": len(set(ranked_ids) - set(original_ids)),
            "candidate_removals": len(set(original_ids) - set(ranked_ids)),
            "source_modifications": 0 if source_unchanged else 1,
            "benchmark_relevance_grade_used": False,
            "score_breakdown": breakdown,
        }

    @staticmethod
    def _normalize(value: float, values: list[float]) -> float:
        maximum = max(values, default=0.0)
        return 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))

    @staticmethod
    def _channel_score(item: QueryAwareCandidate, names: tuple[str, ...]) -> float:
        values = [
            float(value) for key, value in item.raw_scores.items()
            if any(name in key.upper() for name in names) and isinstance(value, (int, float))
        ]
        if values:
            return max(values)
        return 1.0 if any(any(name in channel.upper() for name in names) for channel in item.source_channels) else 0.0

    @classmethod
    def _semantic_score(cls, item: QueryAwareCandidate) -> float:
        return max(cls._channel_score(item, ("SEMANTIC_UNIT", "SEMANTIC")), 1.0 if item.semantic_unit_id else 0.0)

    @staticmethod
    def _citation_quality(item: QueryAwareCandidate, status: dict[str, bool] | None) -> float:
        if status is not None:
            return 1.0 if status.get(item.chunk_id, False) else 0.0
        return 1.0 if item.scope_validation_passed and (item.source_locator or item.section_title or item.page_number is not None) else 0.0

    @staticmethod
    def _source_quality(item: QueryAwareCandidate) -> float:
        metadata = getattr(item.document, "metadata_json", None) or {}
        official = bool(metadata.get("official_domain") or metadata.get("is_official_source") or item.scope_validation_passed)
        return 1.0 if official and item.scope_validation_passed else 0.5 if item.scope_validation_passed else 0.0

    @staticmethod
    def _term_overlap(terms: list[str], content: str) -> float:
        cleaned = [term.strip().lower() for term in terms if term.strip()]
        if not cleaned:
            return 0.0
        lowered = (content or "").lower()
        return sum(term in lowered for term in cleaned) / len(cleaned)

    @classmethod
    def _intent_match(
        cls,
        item: QueryAwareCandidate,
        understanding: QueryUnderstandingResult,
        *,
        query_support: float = 0.0,
    ) -> float:
        text = f"{item.section_title or ''} {item.content}".lower()
        requested = cls.requested_information_support(text, understanding.requested_information)
        requested_score = len(requested) / max(1, len(set(understanding.requested_information)))
        entity_score = cls._term_overlap(
            [*understanding.symptoms, *understanding.alarm_names, *understanding.components], text
        )
        contextual_score = cls._contextual_intent_evidence_score(
            item,
            understanding,
            query_support=query_support,
        )
        context_sensitive = {
            "CAUSE", "CONFIGURATION", "SAFETY", "VERIFICATION", "PREREQUISITE",
        }
        calculation_procedure = (
            "PROCEDURE" in understanding.requested_information
            and any(
                term in cls._compact_match_text(
                    understanding.original_query or understanding.normalized_query
                )
                for term in ("计算", "换算", "百分比", "数量", "位置")
            )
        )
        if context_sensitive.intersection(understanding.requested_information) or calculation_procedure:
            return max(contextual_score, contextual_score * 0.80 + entity_score * 0.20)
        return max(requested_score, entity_score)

    @classmethod
    def _contextual_intent_evidence_score(
        cls,
        item: QueryAwareCandidate,
        understanding: QueryUnderstandingResult,
        *,
        query_support: float = 0.0,
    ) -> float:
        text = cls._compact_match_text(f"{item.section_title or ''} {item.content}")
        query = cls._compact_match_text(
            understanding.original_query or understanding.normalized_query
        )
        requested = set(understanding.requested_information)
        scores: list[float] = []

        if "CAUSE" in requested:
            markers = cls.SUPPORT_TERMS["CAUSE"]
            marker_score = float(any(term in text for term in markers))
            relevant_terms = list(dict.fromkeys([
                *understanding.symptoms,
                *understanding.components,
                *understanding.alarm_names,
            ]))
            relevant_score = cls._term_overlap(relevant_terms, text) if relevant_terms else 0.0
            relevant_score = max(relevant_score, min(1.0, query_support * 1.5))
            if relevant_score == 0.0:
                scores.append(marker_score * 0.80 if len(relevant_terms) < 3 else 0.0)
            else:
                scores.append(min(1.0, relevant_score * 0.60 + marker_score * 0.40))

        if "CONFIGURATION" in requested:
            config_marker = any(term in text for term in cls.SUPPORT_TERMS["CONFIGURATION"])
            query_identifiers = [
                value.casefold()
                for value in re.findall(r"[A-Za-z]+[A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+", query)
                if value.casefold() not in {"sun2000", "fusionsolar"}
            ]
            identifier_score = 1.0 if query_identifiers and any(value in text for value in query_identifiers) else 0.0
            communication_score = cls._term_overlap(
                [*understanding.components, *understanding.symptoms], text
            )
            if query_identifiers:
                scores.append(min(1.0, 0.35 * float(config_marker) + 0.40 * identifier_score + 0.25 * communication_score))
            else:
                scores.append(min(1.0, 0.35 * float(config_marker) + 0.65 * communication_score))

        if "SAFETY" in requested:
            scores.append(cls._safety_intent_score(query, text))

        if "VERIFICATION" in requested:
            scores.append(cls._verification_intent_score(query, text))

        if "PREREQUISITE" in requested:
            marker_score = float(any(term in text for term in cls.SUPPORT_TERMS["PREREQUISITE"]))
            action_score = float(any(term in text for term in ("操作前", "安装前", "下电后", "确认", "检查")))
            scores.append((marker_score + action_score) / 2.0)

        if "PROCEDURE" in requested and any(
            term in query for term in ("计算", "换算", "百分比", "数量", "位置")
        ):
            scores.append(cls._calculation_evidence_score(query, text))

        if not scores:
            return 0.0
        return max(0.0, min(1.0, sum(scores) / len(scores)))

    @staticmethod
    def _calculation_evidence_score(query: str, text: str) -> float:
        if not any(term in query for term in ("计算", "换算", "百分比", "数量", "位置")):
            return 0.0
        checks = [
            "百分比" in text,
            any(term in text for term in ("总数量", "组件总数", "组件数量", "光伏组件组成")),
            any(term in text for term in ("疑似故障位置", "故障位置")),
            any(term in text for term in ("计算", "换算", "=", "×", "x")),
        ]
        return sum(checks) / len(checks)

    @staticmethod
    def _safety_intent_score(query: str, text: str) -> float:
        groups: list[list[bool]] = []
        if any(term in query for term in ("带电", "拆装", "拆除", "线缆")):
            groups.append([
                any(term in text for term in ("带电", "断电", "下电", "电源")),
                any(term in text for term in ("严禁", "禁止", "不得", "不允许")),
                any(term in text for term in ("线缆", "端子", "安装", "拆除", "连接器")),
                any(term in text for term in ("绝缘工具", "绝缘手套", "个人防护", "防护用品", "防护用具")),
            ])
        if any(term in query for term in ("下电", "等待", "交直流", "直流侧", "交流侧")):
            groups.append([
                any(term in text for term in ("下电", "断开", "关闭", "off")),
                any(term in text for term in ("等待", "分钟", "min", "秒")),
                "交流" in text and "直流" in text,
                any(term in text for term in ("测量", "万用表", "钳形表", "验电", "电压", "电流")),
            ])
        if not groups:
            return float(any(term in text for term in ("安全", "危险", "触电", "防护", "断电")))
        scores = [1.0 if all(checks) else 0.0 for checks in groups]
        return sum(scores) / len(scores)

    @staticmethod
    def _verification_intent_score(query: str, text: str) -> float:
        checks = [
            any(term in text for term in ("确认", "测量", "检查", "验证", "确定")),
        ]
        if any(term in query for term in ("等待", "多久", "下电")):
            checks.append(any(term in text for term in ("等待", "分钟", "min", "秒")))
        if any(term in query for term in ("交直流", "交流侧", "直流侧")):
            checks.extend([
                "交流" in text and "直流" in text,
                any(term in text for term in ("万用表", "钳形表", "验电", "电压", "电流")),
            ])
        return sum(checks) / len(checks)

    @classmethod
    def _document_purpose_match(
        cls,
        item: QueryAwareCandidate,
        understanding: QueryUnderstandingResult,
    ) -> float:
        query = cls._compact_match_text(
            understanding.original_query or understanding.normalized_query
        )
        document_type = str(getattr(item.document, "document_type", "") or "").upper()
        content = cls._compact_match_text(item.content or "")
        if any(term in query for term in ("多少", "数量", "几路")):
            if "数量" in content and re.search(r"\d+", content):
                return 1.0
        if any(term in query for term in ("覆盖", "机型", "型号")) and understanding.device_models:
            if any(term in content for term in ("本文主要涉及以下产品型号", "涉及以下产品型号", "适用型号")):
                return 1.0
        if any(term in query for term in ("安装", "拆装", "拆除", "接线", "线缆")):
            return 1.0 if "INSTALLATION" in document_type else 0.0
        if any(term in query for term in ("例行维护", "维护", "检修")):
            return 1.0 if any(term in document_type for term in ("MAINTENANCE", "SERVICE")) else 0.0
        return 0.0

    @staticmethod
    def _entity_match(item: QueryAwareCandidate, understanding: QueryUnderstandingResult) -> float:
        values = []
        if understanding.device_models:
            values.append(1.0 if item.exact_model_match else 0.0)
        if understanding.alarm_codes or understanding.alarm_names:
            values.append(1.0 if item.exact_alarm_match else 0.0)
        return sum(values) / len(values) if values else 1.0

    @classmethod
    def _conflict_penalty(cls, item: QueryAwareCandidate, understanding: QueryUnderstandingResult) -> tuple[float, list[str]]:
        metadata: dict[str, Any] = {}
        for source in (getattr(item.chunk, "metadata_json", None), getattr(item.document, "metadata_json", None)):
            if isinstance(source, dict):
                metadata.update(source)
        candidate_models = {
            cls._normalize_model_identifier(value)
            for value in cls._values(metadata, "device_models", "device_model", "applicable_device_models")
        }
        candidate_alarms = cls._values(metadata, "alarm_codes", "alarm_code")
        if not candidate_models:
            candidate_models = {
                cls._normalize_model_identifier(value)
                for value in cls.MODEL_PATTERN.findall(item.content or "")
            }
        if not candidate_alarms:
            candidate_alarms = {value.upper() for value in cls.ALARM_PATTERN.findall(item.content or "")}
        expected_models = {
            cls._normalize_model_identifier(value)
            for value in understanding.device_models
            if cls._normalize_model_identifier(value) != "SUN2000"
        }
        expected_alarms = {value.upper() for value in understanding.alarm_codes}
        penalty = 0.0
        reasons: list[str] = []
        if expected_models and candidate_models and expected_models.isdisjoint(candidate_models) and not item.exact_model_match:
            penalty += cls.ENTITY_CONFLICT_PENALTY
            reasons.append("TRUE_MODEL_CONFLICT")
        if expected_alarms and candidate_alarms and expected_alarms.isdisjoint(candidate_alarms) and not item.exact_alarm_match:
            penalty += cls.EVIDENCE_CONFLICT_PENALTY
            reasons.append("TRUE_ALARM_CONFLICT")
        return min(1.0, penalty), reasons

    @staticmethod
    def _values(metadata: dict[str, Any], *keys: str) -> set[str]:
        values: set[str] = set()
        for key in keys:
            value = metadata.get(key)
            items = value if isinstance(value, list) else [value] if value else []
            values.update(str(item).strip().upper() for item in items if str(item).strip())
        return values

    @staticmethod
    def _content_hash(content: str) -> str:
        normalized = "".join((content or "").lower().split())[:1000]
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_model_identifier(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value).upper())
