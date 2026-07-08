from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any


class TextVectorService:
    """Small dependency-free lexical vectors for first-version local retrieval."""

    VECTOR_VERSION = "lexical_sparse_v1"
    MAX_TERMS = 240

    _ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+\-./]{1,}", re.IGNORECASE)
    _CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
    _STOP_TERMS = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "page",
        "image",
        "manual",
        "用户",
        "手册",
        "图片",
        "说明",
        "页面",
        "本文",
    }

    def metadata_for_text(self, text: str, base_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = dict(base_metadata or {})
        vector = self.vectorize(text)
        metadata["text_vector"] = {
            "version": self.VECTOR_VERSION,
            "terms": vector,
            "term_count": len(vector),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._contains_image_context(text):
            metadata["source_modalities"] = sorted(
                set(metadata.get("source_modalities") or []) | {"text", "image_ocr_caption"}
            )
        else:
            metadata["source_modalities"] = sorted(set(metadata.get("source_modalities") or []) | {"text"})
        return metadata

    def vectorize(self, text: str) -> dict[str, float]:
        counter = Counter(self._tokens(text))
        if not counter:
            return {}

        weighted: dict[str, float] = {}
        for term, count in counter.items():
            weighted[term] = 1.0 + math.log(count)

        top_terms = sorted(weighted.items(), key=lambda item: item[1], reverse=True)[: self.MAX_TERMS]
        norm = math.sqrt(sum(weight * weight for _, weight in top_terms))
        if norm <= 0:
            return {}
        return {term: round(weight / norm, 6) for term, weight in top_terms}

    def vector_from_metadata(self, metadata: dict[str, Any] | None) -> dict[str, float]:
        if not isinstance(metadata, dict):
            return {}
        vector_payload = metadata.get("text_vector")
        if not isinstance(vector_payload, dict):
            return {}
        if vector_payload.get("version") != self.VECTOR_VERSION:
            return {}
        terms = vector_payload.get("terms")
        if not isinstance(terms, dict):
            return {}
        vector: dict[str, float] = {}
        for term, value in terms.items():
            try:
                vector[str(term)] = float(value)
            except (TypeError, ValueError):
                continue
        return vector

    @staticmethod
    def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        if len(left) > len(right):
            left, right = right, left
        return sum(weight * right.get(term, 0.0) for term, weight in left.items())

    def _tokens(self, text: str) -> list[str]:
        normalized = (text or "").lower()
        tokens: list[str] = []
        for token in self._ASCII_TOKEN_RE.findall(normalized):
            cleaned = token.strip("._-/")
            if len(cleaned) >= 2 and cleaned not in self._STOP_TERMS:
                tokens.append(cleaned)

        for run in self._CJK_RUN_RE.findall(normalized):
            tokens.extend(self._cjk_ngrams(run, 2))
            tokens.extend(self._cjk_ngrams(run, 3))

        return [token for token in tokens if token not in self._STOP_TERMS]

    @staticmethod
    def _cjk_ngrams(text: str, size: int) -> list[str]:
        if len(text) < size:
            return []
        return [text[index : index + size] for index in range(0, len(text) - size + 1)]

    @staticmethod
    def _contains_image_context(text: str) -> bool:
        return any(marker in text for marker in ["图片 OCR", "图片说明", "image", "ocr"])
