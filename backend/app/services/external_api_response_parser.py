from __future__ import annotations

import json
from typing import Any

from app.services.multimodal_result_normalizer import MultimodalResultNormalizer


class ExternalApiResponseParser:
    @staticmethod
    def parse(raw_response: Any, capability: str) -> dict[str, Any]:
        if raw_response is None:
            parsed: dict[str, Any] = {}
        elif isinstance(raw_response, dict):
            parsed = raw_response
        elif isinstance(raw_response, str):
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                parsed = {"raw_text": raw_response}
        else:
            parsed = {"raw_response": str(raw_response)}
        if capability in {"text_chat", "structured_extract", "safety_review"}:
            text = ""
            for key in ("text", "raw_text", "result", "content", "summary"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
            normalized = {
                "text": text,
                "summary": parsed.get("summary") or text[:500],
                "raw_text": parsed.get("raw_text") or text,
                "real_external_api_used": bool(parsed.get("real_external_api_used")),
                "mocked": bool(parsed.get("mocked")),
                "needs_human_review": bool(parsed.get("needs_human_review", True)),
            }
        else:
            normalized = MultimodalResultNormalizer.normalize(capability, parsed)
        return {**parsed, "normalized_result": normalized}
