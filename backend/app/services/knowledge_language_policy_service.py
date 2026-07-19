from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.core.config import get_settings


ZH_ALIASES = {"zh", "zh-cn", "zh_cn", "chinese", "中文", "简体中文"}
EN_ALIASES = {"en", "en-us", "en_us", "english", "英文"}


@dataclass(frozen=True, slots=True)
class LanguageAssessment:
    normalized_language: str
    chinese_ratio: float
    is_default_retrieval_language: bool
    is_pilot_eligible: bool
    reason: str | None


class KnowledgeLanguagePolicyService:
    """Chinese-primary policy for official knowledge without translating content."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def normalize_language(value: str | None) -> str:
        normalized = (value or "").strip().lower()
        if normalized in ZH_ALIASES:
            return "zh-CN"
        if normalized in EN_ALIASES:
            return "en"
        if normalized in {"bilingual", "zh-en", "zh/en", "中英双语"}:
            return "bilingual"
        return "unknown"

    @staticmethod
    def chinese_ratio(text: str | None) -> float:
        text = text or ""
        cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))
        latin = len(re.findall(r"[A-Za-z]", text))
        return round(cjk / (cjk + latin), 6) if cjk + latin else 0.0

    def assess(self, *, declared_language: str | None, title: str, content: str) -> LanguageAssessment:
        declared = self.normalize_language(declared_language)
        ratio = self.chinese_ratio(content)
        latin = len(re.findall(r"[A-Za-z]", content or ""))
        cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", content or ""))
        if declared == "bilingual" or (cjk >= 100 and latin >= 100 and 0.35 <= ratio < 0.60):
            language = "bilingual"
        elif declared == "zh-CN" and ratio >= 0.35:
            language = "zh-CN"
        elif ratio >= 0.60:
            language = "zh-CN"
        elif declared == "en" or (latin > cjk and latin >= 20):
            language = "en"
        else:
            language = "unknown"
        default = language == self.settings.KNOWLEDGE_PRIMARY_LANGUAGE
        pilot = default
        reason = None if default else (
            "english_disabled_current_stage" if language == "en" else
            "bilingual_requires_individual_quality_review" if language == "bilingual" else
            "language_unverified"
        )
        return LanguageAssessment(language, ratio, default, pilot, reason)

    def policy_metadata(self, *, metadata: dict | None, title: str, content: str) -> dict:
        result = dict(metadata or {})
        assessment = self.assess(
            declared_language=str(result.get("language") or ""), title=title, content=content,
        )
        group_seed = str(result.get("language_group_seed") or result.get("source_nid") or title).strip().lower()
        group_id = result.get("language_group_id") or f"lg_{hashlib.sha256(group_seed.encode('utf-8')).hexdigest()[:20]}"
        result.update({
            "language": assessment.normalized_language,
            "normalized_language": assessment.normalized_language,
            "primary_language": self.settings.KNOWLEDGE_PRIMARY_LANGUAGE,
            "alternate_language": "en" if assessment.normalized_language == "en" else None,
            "translation_status": "original_vendor_language",
            "language_group_id": group_id,
            "is_default_retrieval_language": assessment.is_default_retrieval_language,
            "is_pilot_eligible": assessment.is_pilot_eligible,
            "language_exclusion_reason": assessment.reason,
            "chinese_character_ratio": assessment.chinese_ratio,
        })
        return result
