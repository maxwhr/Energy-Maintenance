from __future__ import annotations

from typing import Any

from app.services.external_api_adapters.base import ExternalApiAdapter, ExternalApiAdapterResult


class BlockedAdapter(ExternalApiAdapter):
    def check_status(self) -> ExternalApiAdapterResult:
        if not self.provider.enabled:
            return ExternalApiAdapterResult(
                status="disabled",
                success=False,
                message=f"{self.provider.provider_code} is disabled.",
                blocked_reason="provider_disabled",
            )
        return ExternalApiAdapterResult(
            status="blocked",
            success=False,
            message=f"{self.provider.provider_code} is reserved but real external calls are blocked.",
            blocked_reason="real_external_call_disabled",
        )

    def _dry_run(self, capability: str, request_summary: dict[str, Any]) -> ExternalApiAdapterResult:
        return ExternalApiAdapterResult(
            status="blocked",
            success=False,
            provider_code=self.provider.provider_code,
            capability=capability,
            model_name=self.config.get("model_name") or self.provider.default_model_name,
            would_call=False,
            external_api_called=False,
            blocked_reason="real_external_call_disabled",
            message=f"{self.provider.provider_code} is reserved for {capability}; no external call was attempted.",
            request_summary=self.sanitize_request(request_summary),
            response_summary={
                "capability": capability,
                "dry_run": True,
                "provider_type": self.provider.provider_type,
            },
        )
