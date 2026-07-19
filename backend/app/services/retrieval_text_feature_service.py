from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalTextFeatures:
    normalized: str
    compact: str
    tokens: frozenset[str]
    model_identifiers: frozenset[str]
    alarm_codes: frozenset[str]
    parameter_terms: frozenset[str]
    content_fingerprint: str
    near_duplicate_fingerprint: str


class RetrievalTextFeatureService:
    """Shared, label-free lexical features for candidate generation and ranking."""

    MODEL_PATTERN = re.compile(
        r"(?<![A-Z0-9])(?:SUN\s*2000[\s_./（）()\-]*)?"
        r"(?P<power>\d{1,3}\s*K\s*T\s*L)"
        r"(?:[\s_./（）()\-]*(?P<suffix>(?:M\s*[0-9]|H\s*[0-9](?:\+\+)?|NH|E\s*\d{3}|A|MG\s*[0-9])))?"
        r"(?![A-Z0-9+])",
        re.IGNORECASE,
    )
    ALARM_PATTERN = re.compile(r"(?<![A-Z0-9])(?:A\d{3,5}|20\d{2}|21\d{2})(?![A-Z0-9])", re.IGNORECASE)
    ASCII_TOKEN_PATTERN = re.compile(r"[a-z]+(?:[._/+\-]?[a-z0-9]+)*|\d+(?:\.\d+)?(?:a|v|w|kw|ma|mm|℃|%)?", re.IGNORECASE)
    CHINESE_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")
    PARAMETER_TERMS = frozenset({
        "mppt", "rs485", "modbus", "lvrt", "低电压穿越", "高电压穿越", "绝缘阻抗",
        "绝缘电阻", "通信断链关机时间", "额定输出功率", "最大输入电压", "开路电压",
        "短路电流", "组串电流", "直流输入", "交流输出", "电网电压", "功率因数",
        "无功功率", "波特率", "afci", "pid", "漏电动作电流", "环境温度", "风扇",
    })

    @classmethod
    def build(cls, value: str) -> RetrievalTextFeatures:
        normalized = cls.normalize_text(value)
        compact = cls.compact_text(normalized)
        tokens = cls.tokenize(normalized)
        models = cls.extract_model_identifiers(normalized)
        alarms = frozenset(match.group(0).upper() for match in cls.ALARM_PATTERN.finditer(normalized))
        parameters = frozenset(term for term in cls.PARAMETER_TERMS if term in normalized)
        fingerprint_source = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)
        near_source = cls._near_duplicate_source(normalized)
        return RetrievalTextFeatures(
            normalized=normalized,
            compact=compact,
            tokens=tokens,
            model_identifiers=models,
            alarm_codes=alarms,
            parameter_terms=parameters,
            content_fingerprint=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
            near_duplicate_fingerprint=hashlib.sha256(near_source.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def normalize_text(value: str) -> str:
        value = unicodedata.normalize("NFKC", str(value or "")).casefold()
        value = value.translate(str.maketrans({"‐": "-", "‑": "-", "–": "-", "—": "-", "_": "-"}))
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def compact_text(value: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff+]+", "", str(value or "").casefold())

    @classmethod
    def tokenize(cls, value: str) -> frozenset[str]:
        tokens = {match.group(0).casefold() for match in cls.ASCII_TOKEN_PATTERN.finditer(value)}
        for match in cls.CHINESE_RUN_PATTERN.finditer(value):
            run = match.group(0)
            tokens.add(run)
            if len(run) > 2:
                tokens.update(run[index:index + 2] for index in range(len(run) - 1))
        return frozenset(token for token in tokens if token)

    @classmethod
    def extract_model_identifiers(cls, value: str) -> frozenset[str]:
        models: set[str] = set()
        for match in cls.MODEL_PATTERN.finditer(unicodedata.normalize("NFKC", str(value or "")).upper()):
            power = re.sub(r"\s+", "", match.group("power").upper())
            suffix = re.sub(r"\s+", "", (match.group("suffix") or "").upper())
            models.add(f"SUN2000{power}{suffix}")
        return frozenset(models)

    @classmethod
    def normalize_model_identifier(cls, value: str) -> str:
        extracted = cls.extract_model_identifiers(value)
        if len(extracted) == 1:
            return next(iter(extracted))
        return re.sub(r"[^A-Z0-9+]", "", unicodedata.normalize("NFKC", str(value or "")).upper())

    @classmethod
    def exact_model_match(cls, expected: str, candidate_models: frozenset[str]) -> bool:
        normalized = cls.normalize_model_identifier(expected)
        if not normalized or normalized == "SUN2000":
            return False
        if normalized in candidate_models:
            return True
        if re.fullmatch(r"SUN2000\d{1,3}KTL", normalized):
            return any(
                candidate == normalized
                or re.fullmatch(rf"{re.escape(normalized)}(?:M\d|H\d(?:\+\+)?|NH|E\d{{3}}|A|MG\d)", candidate)
                for candidate in candidate_models
            )
        return False

    @staticmethod
    def _near_duplicate_source(value: str) -> str:
        value = re.sub(r"文档版本\s*\d+[^\n]{0,80}", "", value)
        value = re.sub(r"版权所有[^\n]{0,80}", "", value)
        value = re.sub(r"\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b", "", value)
        value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)
        return value[:1400]
