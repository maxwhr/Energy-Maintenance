from __future__ import annotations

import time
from typing import Any

from app.services.external_api_adapters.base import ExternalApiAdapter, ExternalApiAdapterResult
from app.services.external_api_prompt_templates import prompt_for_capability


class OcrApiAdapter(ExternalApiAdapter):
    api_style = "ocr_http_json"

    def invoke_ocr(self, request_summary: dict) -> ExternalApiAdapterResult:
        return self.invoke(request_summary, capability="ocr", dry_run=True)

    def invoke(self, payload: dict, *, capability: str, dry_run: bool = True, mock_run: bool = False) -> ExternalApiAdapterResult:
        if not dry_run and not mock_run:
            return self._invoke_real(payload, capability=capability)
        result = super().invoke(payload, capability=capability, dry_run=dry_run, mock_run=mock_run)
        result.response_summary = {
            **result.response_summary,
            "adapter": "ocr_api",
            "supported_capabilities": ["ocr", "nameplate_extract", "alarm_screen_analysis"],
            "future_real_invoke_entry": "OcrApiAdapter.invoke",
        }
        if result.status == "would_call":
            result.message = "OCR API request was built and sanitized; no OCR API call was made."
        return result

    def _invoke_real(self, payload: dict[str, Any], *, capability: str) -> ExternalApiAdapterResult:
        request_summary = self.sanitize_request(self.build_request(capability, payload))
        status = self.check_status()
        if status.status in {"disabled", "not_configured"}:
            status.capability = capability
            status.request_summary = request_summary
            status.response_summary = self.sanitize_response(status.response_summary)
            return status
        if not self.config.get("real_external_calls_enabled"):
            return ExternalApiAdapterResult(
                status="configured_but_real_call_not_allowed",
                success=False,
                provider_code=self.provider.provider_code,
                capability=capability,
                model_name=self.config.get("model_name") or self.provider.default_model_name,
                would_call=True,
                blocked_reason="real_call_not_allowed",
                message="OCR API provider requires explicit allow_real_api for real calls.",
                request_summary=request_summary,
            )

        started = time.perf_counter()
        try:
            if str(self.config.get("api_profile") or "").startswith("openai"):
                raw_response = self._json_request(
                    url=self._chat_completions_url(str(self.config.get("base_url") or "")),
                    payload=self._vision_ocr_payload(payload),
                    api_key=str(self.config.get("api_key") or ""),
                    timeout_seconds=int(self.config.get("timeout_seconds") or 60),
                )
                content = self._extract_text_content(raw_response)
                parsed_content = self._json_or_text(content) if content else raw_response
            else:
                raw_response = self._json_request(
                    url=str(self.config.get("base_url") or ""),
                    payload=self._custom_ocr_payload(payload),
                    api_key=str(self.config.get("api_key") or ""),
                    timeout_seconds=int(self.config.get("timeout_seconds") or 60),
                )
                parsed_content = raw_response
            parsed = self.parse_response(
                {
                    **parsed_content,
                    "real_external_api_used": True,
                    "mocked": False,
                },
                "ocr",
            )
            normalized = parsed.get("normalized_result", {})
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ExternalApiAdapterResult(
                status="succeeded",
                success=True,
                provider_code=self.provider.provider_code,
                capability="ocr",
                model_name=str(self.config.get("model_name") or self.provider.default_model_name),
                external_api_called=True,
                latency_ms=latency_ms,
                message="OCR API real call succeeded; human review is still required.",
                request_summary=request_summary,
                response_summary=self.sanitize_response(
                    {
                        "adapter": "ocr_api",
                        "response_keys": sorted(raw_response.keys()),
                        "real_external_api_used": True,
                        "normalized_result": normalized,
                    }
                ),
                normalized_result=normalized,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ExternalApiAdapterResult(
                status="failed",
                success=False,
                provider_code=self.provider.provider_code,
                capability="ocr",
                model_name=str(self.config.get("model_name") or self.provider.default_model_name),
                external_api_called=True,
                latency_ms=latency_ms,
                error_code="provider_call_failed",
                error_message=self._sanitize_error(str(exc)),
                message="OCR API real call failed; media management must remain available.",
                request_summary=request_summary,
                response_summary={"adapter": "ocr_api", "real_external_api_used": True},
            )

    def _vision_ocr_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt_for_capability("ocr")}]
        content.extend(self._image_content(payload))
        return {
            "model": self.config.get("model_name") or self.provider.default_model_name,
            "messages": [
                {"role": "system", "content": "You extract visible text from PV inverter maintenance images. Return JSON only."},
                {"role": "user", "content": content},
            ],
            "temperature": self.config.get("temperature") or 0,
            "max_tokens": self.config.get("max_tokens") or 1024,
        }

    def _custom_ocr_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.config.get("model_name") or self.provider.default_model_name,
            "language": payload.get("language") or "chi_sim+eng",
            "prompt": prompt_for_capability("ocr"),
            "images": [
                {"mime_type": item["mime_type"], "data": item["data_url"].split(",", 1)[-1]}
                for item in self._image_content(payload, custom=True)
            ],
        }

    @staticmethod
    def _image_content(payload: dict[str, Any], *, custom: bool = False) -> list[dict[str, Any]]:
        input_summary = payload.get("input_summary") if isinstance(payload.get("input_summary"), dict) else {}
        raw_images = payload.get("images") or input_summary.get("images") or []
        if not raw_images and (payload.get("image_base64") or input_summary.get("image_base64")):
            raw_images = [
                {
                    "image_base64": payload.get("image_base64") or input_summary.get("image_base64"),
                    "mime_type": payload.get("mime_type") or input_summary.get("mime_type") or "image/png",
                }
            ]
        result: list[dict[str, Any]] = []
        for item in raw_images[:3] if isinstance(raw_images, list) else []:
            if not isinstance(item, dict):
                continue
            image = item.get("image_base64") or item.get("data") or item.get("base64")
            if not isinstance(image, str) or not image.strip():
                continue
            mime_type = str(item.get("mime_type") or "image/png")
            data_url = image if image.startswith("data:image/") else f"data:{mime_type};base64,{image}"
            if custom:
                result.append({"mime_type": mime_type, "data_url": data_url})
            else:
                result.append({"type": "image_url", "image_url": {"url": data_url}})
        return result
