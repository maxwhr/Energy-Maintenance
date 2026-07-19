from types import SimpleNamespace

import pytest

from app.services.external_api_adapters.base import ExternalApiAdapter
from app.services.external_api_adapters.mimo_multimodal_adapter import MimoMultimodalAdapter
from app.services.external_api_response_parser import ExternalApiResponseParser
from app.services.multimodal_result_normalizer import MultimodalResultNormalizer


def test_adapter_parses_markdown_fenced_json() -> None:
    result = ExternalApiAdapter._json_or_text('```json\n{"alarm_codes":["225"]}\n```')
    assert result == {"alarm_codes": ["225"]}


def test_response_parser_parses_markdown_fenced_json() -> None:
    result = ExternalApiResponseParser.parse('```json\n{"visible_text":"Error 225"}\n```', "alarm_screen_analysis")
    normalized = result["normalized_result"]
    assert normalized["visible_text"] == ["Error 225"]
    assert normalized["needs_human_review"] is True
    assert normalized["root_cause_determined"] is False


def test_normalizer_recovers_embedded_json_and_provider_aliases() -> None:
    result = MultimodalResultNormalizer.normalize_multimodal(
        "alarm_screen_analysis",
        {
            "raw_text": """```json
            {
              "visible_message": "PV IsolationLow",
              "alarm_codes": ["225"],
              "device_info": {"manufacturer": "Huawei", "product_series": "SUN2000"},
              "visible_display_findings": ["Red alarm icon is visible"],
              "safe_follow_up_checks": ["Confirm the alarm in FusionSolar"],
              "safety_warnings": ["Do not open the enclosure while energized"],
              "confidence": 0.84,
              "needs_human_review": false,
              "root_cause_determined": true
            }
            ```""",
            "real_external_api_used": True,
        },
    )
    assert result["visible_text"] == ["PV IsolationLow"]
    assert result["detected_alarm_codes"] == ["225"]
    assert result["detected_device_info"]["manufacturer"] == "Huawei"
    assert result["visual_findings"] == ["Red alarm icon is visible"]
    assert result["recommended_next_steps"] == ["Confirm the alarm in FusionSolar"]
    assert result["safety_risks"] == ["Do not open the enclosure while energized"]
    assert result["confidence"] == 0.84
    assert result["real_external_api_used"] is True
    assert result["needs_human_review"] is True
    assert result["root_cause_determined"] is False


def test_normalizer_keeps_plain_text_when_json_is_invalid() -> None:
    result = MultimodalResultNormalizer.normalize_multimodal(
        "fault_scene_analysis",
        {"raw_text": "provider returned a plain-language observation"},
    )
    assert result["raw_text"] == "provider returned a plain-language observation"
    assert result["needs_human_review"] is True
    assert result["root_cause_determined"] is False


def _mimo_adapter(*, enabled: bool = True) -> MimoMultimodalAdapter:
    provider = SimpleNamespace(
        provider_code="mimo_2_5",
        provider_type="multimodal_model",
        default_model_name="mimo-2.5",
        enabled=enabled,
        requires_api_key=True,
        base_url_env_key="MIMO_BASE_URL",
        api_key_env_key="MIMO_API_KEY",
        model_env_key="MIMO_MODEL",
    )
    return MimoMultimodalAdapter(
        provider,
        {
            "base_url": "https://provider.invalid/v1",
            "api_key": "task30a-unit-test-secret",
            "api_key_configured": True,
            "model_name": "mimo-2.5",
            "timeout_seconds": 10,
            "real_external_calls_enabled": True,
            "api_profile": "openai_compatible_vision",
        },
    )


def test_mimo_disabled_provider_does_not_call_network(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _mimo_adapter(enabled=False)
    network = pytest.fail
    monkeypatch.setattr(adapter, "_json_request", network)
    result = adapter.invoke({}, capability="fault_scene_analysis", dry_run=False)
    assert result.status == "disabled"
    assert result.external_api_called is False


def test_mimo_timeout_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _mimo_adapter()
    monkeypatch.setattr(
        adapter,
        "_json_request",
        lambda **_: (_ for _ in ()).throw(TimeoutError("task30a-unit-test-secret timed out")),
    )
    result = adapter.invoke({}, capability="fault_scene_analysis", dry_run=False)
    assert result.status == "failed"
    assert result.error_code == "provider_call_failed"
    assert "task30a-unit-test-secret" not in (result.error_message or "")


def test_mimo_empty_response_is_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _mimo_adapter()
    monkeypatch.setattr(adapter, "_json_request", lambda **_: {})
    result = adapter.invoke({}, capability="fault_scene_analysis", dry_run=False)
    assert result.status == "failed"
    assert result.error_message == "provider returned an empty response"


def test_low_confidence_remains_review_only() -> None:
    result = MultimodalResultNormalizer.normalize_multimodal(
        "fault_scene_analysis",
        {"visual_findings": ["Image is too dark"], "confidence": 0.12},
    )
    assert result["confidence"] == 0.12
    assert result["needs_human_review"] is True
    assert result["root_cause_determined"] is False
