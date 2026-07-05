from __future__ import annotations

import time
from typing import Any

from app.services.external_api_adapters.base import ExternalApiAdapter, ExternalApiAdapterResult
from app.services.external_api_prompt_templates import prompt_for_capability


class OpenAICompatibleAdapter(ExternalApiAdapter):
    api_style = "openai_compatible"

    def invoke(self, payload: dict, *, capability: str, dry_run: bool = True, mock_run: bool = False) -> ExternalApiAdapterResult:
        if not dry_run and not mock_run:
            return self._invoke_real(payload, capability=capability)
        result = super().invoke(payload, capability=capability, dry_run=dry_run, mock_run=mock_run)
        result.response_summary = {
            **result.response_summary,
            "adapter": "openai_compatible",
            "supported_capabilities": ["text_chat", "vision_chat", "structured_extract", "safety_review"],
            "future_real_invoke_entry": "OpenAICompatibleAdapter.invoke",
        }
        if result.status == "would_call":
            result.message = "OpenAI-compatible request was built and sanitized; real external call is disabled."
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
                external_api_called=False,
                blocked_reason="real_call_not_allowed",
                message="Provider is configured, but real external call requires explicit allow_real_api.",
                request_summary=request_summary,
            )

        started = time.perf_counter()
        try:
            raw_response = self._json_request(
                url=self._chat_completions_url(str(self.config.get("base_url") or "")),
                payload=self._real_chat_payload(payload, capability),
                api_key=str(self.config.get("api_key") or ""),
                timeout_seconds=int(self.config.get("timeout_seconds") or 60),
            )
            content = self._extract_text_content(raw_response)
            parsed_content = self._json_or_text(content) if content else {}
            parsed = self.parse_response(
                {
                    **parsed_content,
                    "provider_raw": {
                        "id": raw_response.get("id"),
                        "model": raw_response.get("model"),
                        "usage": raw_response.get("usage") if isinstance(raw_response.get("usage"), dict) else None,
                    },
                    "real_external_api_used": True,
                    "mocked": False,
                },
                capability,
            )
            normalized = parsed.get("normalized_result", {})
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ExternalApiAdapterResult(
                status="succeeded",
                success=True,
                provider_code=self.provider.provider_code,
                capability=capability,
                model_name=str(self.config.get("model_name") or self.provider.default_model_name),
                would_call=False,
                external_api_called=True,
                latency_ms=latency_ms,
                message="OpenAI-compatible provider real call succeeded.",
                request_summary=request_summary,
                response_summary=self.sanitize_response(
                    {
                        "adapter": "openai_compatible",
                        "response_keys": sorted(raw_response.keys()),
                        "content_length": len(content),
                        "usage": raw_response.get("usage") if isinstance(raw_response.get("usage"), dict) else None,
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
                capability=capability,
                model_name=str(self.config.get("model_name") or self.provider.default_model_name),
                would_call=False,
                external_api_called=True,
                latency_ms=latency_ms,
                error_code="provider_call_failed",
                error_message=self._sanitize_error(str(exc)),
                message="OpenAI-compatible provider real call failed; fallback should remain available.",
                request_summary=request_summary,
                response_summary={"adapter": "openai_compatible", "real_external_api_used": True},
            )

    def _real_chat_payload(self, payload: dict[str, Any], capability: str) -> dict[str, Any]:
        input_summary = payload.get("input_summary") if isinstance(payload.get("input_summary"), dict) else {}
        messages = payload.get("messages") or input_summary.get("messages")
        if not isinstance(messages, list) or not messages:
            text = self._text_from_payload(payload)
            messages = [
                {"role": "system", "content": prompt_for_capability(capability)},
                {"role": "user", "content": text},
            ]
        return {
            "model": self.config.get("model_name") or self.provider.default_model_name,
            "messages": messages,
            "temperature": self.config.get("temperature"),
            "max_tokens": self.config.get("max_tokens"),
        }

    @staticmethod
    def _text_from_payload(payload: dict[str, Any]) -> str:
        input_summary = payload.get("input_summary") if isinstance(payload.get("input_summary"), dict) else {}
        for key in ("prompt", "question", "text", "input_text"):
            value = payload.get(key) or input_summary.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Analyze Huawei/Sungrow PV inverter maintenance context and return source-aware, safety-conscious output."
