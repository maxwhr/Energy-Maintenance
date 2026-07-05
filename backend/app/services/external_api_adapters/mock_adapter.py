from __future__ import annotations

from typing import Any

from app.services.external_api_adapters.base import ExternalApiAdapter, ExternalApiAdapterResult
from app.services.multimodal_result_normalizer import MultimodalResultNormalizer


class MockAdapter(ExternalApiAdapter):
    def invoke(self, payload: dict[str, Any], *, capability: str, dry_run: bool = False, mock_run: bool = True) -> ExternalApiAdapterResult:
        request_summary = self.sanitize_request(self.build_request(capability, payload))
        if capability == "ocr":
            normalized = MultimodalResultNormalizer.mock_ocr_result(payload)
        else:
            normalized = MultimodalResultNormalizer.mock_multimodal_result(capability, payload)
        return ExternalApiAdapterResult(
            status="mocked",
            success=True,
            provider_code=self.provider.provider_code,
            capability=capability,
            model_name=self.config.get("model_name") or self.provider.default_model_name,
            message=(
                f"{self.provider.provider_code} mock-run completed locally. "
                "No external API was called; result is not for production."
            ),
            would_call=False,
            external_api_called=False,
            request_summary=request_summary,
            response_summary={
                "mocked": True,
                "not_for_production": True,
                "capability": capability,
                "provider_code": self.provider.provider_code,
                "normalized_result": normalized,
            },
            normalized_result=normalized,
        )
