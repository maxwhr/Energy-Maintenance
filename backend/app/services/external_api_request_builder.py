from __future__ import annotations

from typing import Any

from app.services.external_api_prompt_templates import prompt_for_capability
from app.services.external_api_sanitizer import ExternalApiSanitizer


class ExternalApiRequestBuilder:
    @staticmethod
    def build(
        *,
        provider_code: str,
        provider_type: str,
        capability: str,
        payload: dict[str, Any],
        config: dict[str, Any],
        api_style: str = "openai_compatible",
    ) -> dict[str, Any]:
        if capability in {"vision_chat", "fault_scene_analysis", "nameplate_extract", "alarm_screen_analysis"}:
            if api_style == "custom_http_json":
                return ExternalApiRequestBuilder.custom_multimodal_json(
                    provider_code=provider_code,
                    capability=capability,
                    payload=payload,
                    config=config,
                )
            return ExternalApiRequestBuilder.openai_vision_chat(
                provider_code=provider_code,
                capability=capability,
                payload=payload,
                config=config,
            )
        if capability == "ocr":
            return ExternalApiRequestBuilder.ocr_json(
                provider_code=provider_code,
                capability=capability,
                payload=payload,
                config=config,
            )
        return ExternalApiRequestBuilder.openai_text_chat(
            provider_code=provider_code,
            capability=capability,
            payload=payload,
            config=config,
        )

    @staticmethod
    def openai_text_chat(
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        text = ExternalApiRequestBuilder._text_from_payload(payload)
        request = {
            "provider_code": provider_code,
            "api_style": "openai_compatible",
            "endpoint": "/v1/chat/completions",
            "model": config.get("model_name"),
            "messages": [
                {"role": "system", "content": prompt_for_capability(capability)},
                {"role": "user", "content": text},
            ],
            "temperature": config.get("temperature"),
            "max_tokens": config.get("max_tokens"),
            "timeout_seconds": config.get("timeout_seconds"),
        }
        return ExternalApiSanitizer.sanitize(request)

    @staticmethod
    def openai_vision_chat(
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        text = ExternalApiRequestBuilder._text_from_payload(payload)
        image_summary = ExternalApiRequestBuilder._image_summary(payload)
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for _ in range(max(1, image_summary["image_count"])):
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,<redacted>", "image_count": 1},
                }
            )
        request = {
            "provider_code": provider_code,
            "api_style": "openai_compatible_vision",
            "endpoint": "/v1/chat/completions",
            "model": config.get("model_name"),
            "messages": [
                {"role": "system", "content": prompt_for_capability(capability)},
                {"role": "user", "content": content},
            ],
            "temperature": config.get("temperature"),
            "max_tokens": config.get("max_tokens"),
            "timeout_seconds": config.get("timeout_seconds"),
            "image_summary": image_summary,
        }
        return ExternalApiSanitizer.sanitize(request)

    @staticmethod
    def custom_multimodal_json(
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        request = {
            "provider_code": provider_code,
            "api_style": "custom_http_json",
            "base_url_configured": bool(config.get("base_url")),
            "model": config.get("model_name"),
            "capability": capability,
            "prompt": prompt_for_capability(capability),
            "input_text": ExternalApiRequestBuilder._text_from_payload(payload),
            "image_summary": ExternalApiRequestBuilder._image_summary(payload),
            "temperature": config.get("temperature"),
            "max_tokens": config.get("max_tokens"),
            "timeout_seconds": config.get("timeout_seconds"),
        }
        return ExternalApiSanitizer.sanitize(request)

    @staticmethod
    def ocr_json(
        *,
        provider_code: str,
        capability: str,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        request = {
            "provider_code": provider_code,
            "api_style": "ocr_http_json",
            "base_url_configured": bool(config.get("base_url")),
            "model": config.get("model_name"),
            "capability": capability,
            "language": payload.get("language") or "chi_sim+eng",
            "image_summary": ExternalApiRequestBuilder._image_summary(payload),
            "prompt": prompt_for_capability(capability),
            "timeout_seconds": config.get("timeout_seconds"),
        }
        return ExternalApiSanitizer.sanitize(request)

    @staticmethod
    def _text_from_payload(payload: dict[str, Any]) -> str:
        input_summary = payload.get("input_summary") if isinstance(payload.get("input_summary"), dict) else {}
        for key in ("prompt", "question", "text", "input_text"):
            value = payload.get(key) or input_summary.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Analyze the provided photovoltaic inverter maintenance evidence and return structured JSON."

    @staticmethod
    def _image_summary(payload: dict[str, Any]) -> dict[str, Any]:
        input_summary = payload.get("input_summary") if isinstance(payload.get("input_summary"), dict) else {}
        media_ids = payload.get("media_ids") or input_summary.get("media_ids") or []
        image_count = payload.get("image_count") or input_summary.get("image_count")
        if not image_count:
            image_count = len(media_ids) if isinstance(media_ids, list) else 0
        if not image_count and any(key in payload or key in input_summary for key in ("image_base64", "image_data")):
            image_count = 1
        return {
            "image_count": int(image_count or 0),
            "media_ids": [str(item) for item in media_ids[:20]] if isinstance(media_ids, list) else [],
            "mime_type": payload.get("mime_type") or input_summary.get("mime_type"),
            "file_size": payload.get("file_size") or input_summary.get("file_size"),
        }
