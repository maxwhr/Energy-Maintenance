from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.external_api_repository import ExternalApiRepository


DEFAULT_EXTERNAL_API_PROVIDERS = [
    {
        "provider_code": "mimo_2_5",
        "provider_name": "mimo-2.5 multimodal model",
        "provider_type": "multimodal_model",
        "description": "Reserved mimo-2.5 multimodal API provider for PV inverter evidence analysis.",
        "enabled": False,
        "requires_api_key": True,
        "base_url_env_key": "MIMO_BASE_URL",
        "api_key_env_key": "MIMO_API_KEY",
        "model_env_key": "MIMO_MODEL",
        "default_model_name": "mimo-2.5",
        "timeout_seconds": 60,
        "max_tokens": 2048,
        "temperature": 0.1,
        "capabilities_json": [
            "vision_chat",
            "fault_scene_analysis",
            "nameplate_extract",
            "alarm_screen_analysis",
            "structured_extract",
        ],
        "status": "blocked",
        "metadata_json": {
            "real_call_enabled": False,
            "task": "22E",
            "api_profile_env_key": "MIMO_API_PROFILE",
            "supported_api_profiles": ["openai_compatible_vision", "custom_http_json"],
        },
    },
    {
        "provider_code": "cloud_openai",
        "provider_name": "Cloud OpenAI-compatible text model",
        "provider_type": "text_model",
        "description": "Reserved OpenAI-compatible text model API provider.",
        "enabled": False,
        "requires_api_key": True,
        "base_url_env_key": "CLOUD_LLM_BASE_URL",
        "api_key_env_key": "CLOUD_LLM_API_KEY",
        "model_env_key": "CLOUD_LLM_MODEL",
        "default_model_name": None,
        "timeout_seconds": 60,
        "max_tokens": 1024,
        "temperature": 0.2,
        "capabilities_json": ["text_chat", "structured_extract", "safety_review"],
        "status": "not_configured",
        "metadata_json": {"real_call_enabled": False, "task": "22E"},
    },
    {
        "provider_code": "cloud_openai_vision",
        "provider_name": "Cloud OpenAI-compatible vision model",
        "provider_type": "vision_model",
        "description": "Reserved OpenAI-compatible vision model API provider.",
        "enabled": False,
        "requires_api_key": True,
        "base_url_env_key": "CLOUD_VISION_BASE_URL",
        "api_key_env_key": "CLOUD_VISION_API_KEY",
        "model_env_key": "CLOUD_VISION_MODEL",
        "default_model_name": None,
        "timeout_seconds": 60,
        "max_tokens": 2048,
        "temperature": 0.2,
        "capabilities_json": ["vision_chat", "image_caption", "fault_scene_analysis", "structured_extract"],
        "status": "not_configured",
        "metadata_json": {"real_call_enabled": False, "task": "22E"},
    },
    {
        "provider_code": "local_llama_cpp",
        "provider_name": "Local llama.cpp model",
        "provider_type": "local_model",
        "description": "Reserved local llama.cpp OpenAI-compatible text model provider.",
        "enabled": False,
        "requires_api_key": False,
        "base_url_env_key": "LOCAL_LLM_BASE_URL",
        "api_key_env_key": "LOCAL_LLM_API_KEY",
        "model_env_key": "LOCAL_LLM_MODEL",
        "default_model_name": "local-gguf-model",
        "timeout_seconds": 60,
        "max_tokens": 1024,
        "temperature": 0.2,
        "capabilities_json": ["text_chat", "structured_extract"],
        "status": "not_configured",
        "metadata_json": {"real_call_enabled": False, "task": "22E"},
    },
    {
        "provider_code": "tesseract_ocr",
        "provider_name": "Tesseract OCR",
        "provider_type": "ocr_provider",
        "description": "Reserved OCR provider using local Tesseract when installed and enabled.",
        "enabled": False,
        "requires_api_key": False,
        "base_url_env_key": None,
        "api_key_env_key": None,
        "model_env_key": None,
        "default_model_name": "tesseract",
        "timeout_seconds": 30,
        "max_tokens": None,
        "temperature": None,
        "capabilities_json": ["ocr"],
        "status": "disabled",
        "metadata_json": {"real_call_enabled": False, "task": "22E"},
    },
    {
        "provider_code": "custom_ocr_api",
        "provider_name": "Custom OCR API",
        "provider_type": "ocr_provider",
        "description": "Reserved external OCR HTTP API provider.",
        "enabled": False,
        "requires_api_key": True,
        "base_url_env_key": "OCR_API_BASE_URL",
        "api_key_env_key": "OCR_API_KEY",
        "model_env_key": "OCR_API_MODEL",
        "default_model_name": None,
        "timeout_seconds": 60,
        "max_tokens": None,
        "temperature": None,
        "capabilities_json": ["ocr", "nameplate_extract", "alarm_screen_analysis"],
        "status": "not_configured",
        "metadata_json": {"real_call_enabled": False, "task": "22E"},
    },
    {
        "provider_code": "safety_rule_engine",
        "provider_name": "Safety rule engine",
        "provider_type": "safety_provider",
        "description": "Local rule-based safety review provider. It does not call external APIs.",
        "enabled": True,
        "requires_api_key": False,
        "base_url_env_key": None,
        "api_key_env_key": None,
        "model_env_key": None,
        "default_model_name": "rule_based_safety_v1",
        "timeout_seconds": 10,
        "max_tokens": None,
        "temperature": None,
        "capabilities_json": ["safety_review"],
        "status": "available",
        "metadata_json": {"real_call_enabled": False, "local_rule_engine": True, "task": "22E"},
    },
]


DEFAULT_EXTERNAL_API_ROUTES = [
    {
        "route_code": "agent_multimodal_mimo",
        "agent_code": "multimodal_evidence_agent",
        "tool_name": "media_mimo_analysis",
        "capability": "fault_scene_analysis",
        "primary_provider_code": "mimo_2_5",
        "fallback_provider_codes_json": ["cloud_openai_vision"],
        "allow_fallback": True,
        "blocked_when_unconfigured": True,
        "safety_policy_json": {"no_real_external_call": True, "no_base64_logging": True},
        "metadata_json": {"task": "22E", "adapter_contract": "dry_run_and_mock_run"},
    },
    {
        "route_code": "agent_media_ocr",
        "agent_code": None,
        "tool_name": "media_ocr",
        "capability": "ocr",
        "primary_provider_code": "tesseract_ocr",
        "fallback_provider_codes_json": ["custom_ocr_api", "mimo_2_5"],
        "allow_fallback": True,
        "blocked_when_unconfigured": True,
        "safety_policy_json": {"no_real_external_call": True, "no_local_path_logging": True},
        "metadata_json": {"task": "22E", "adapter_contract": "dry_run_and_mock_run"},
    },
    {
        "route_code": "agent_model_chat",
        "agent_code": None,
        "tool_name": "model_gateway_chat",
        "capability": "text_chat",
        "primary_provider_code": "cloud_openai",
        "fallback_provider_codes_json": ["local_llama_cpp"],
        "allow_fallback": True,
        "blocked_when_unconfigured": True,
        "safety_policy_json": {"no_real_external_call": True, "no_secret_logging": True},
        "metadata_json": {"task": "22E", "adapter_contract": "dry_run_and_mock_run"},
    },
    {
        "route_code": "agent_safety_review",
        "agent_code": None,
        "tool_name": "safety_guard",
        "capability": "safety_review",
        "primary_provider_code": "safety_rule_engine",
        "fallback_provider_codes_json": ["cloud_openai"],
        "allow_fallback": True,
        "blocked_when_unconfigured": True,
        "safety_policy_json": {"electrical_safety_first": True},
        "metadata_json": {"task": "22E", "adapter_contract": "dry_run_and_mock_run"},
    },
]


class ExternalApiProviderRegistry:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ExternalApiRepository(db)

    def seed_defaults(self) -> dict[str, int]:
        provider_count = 0
        route_count = 0
        settings = get_settings()
        for values in DEFAULT_EXTERNAL_API_PROVIDERS:
            self.repository.upsert_provider(self._with_runtime_enabled(values, settings))
            provider_count += 1
        for values in DEFAULT_EXTERNAL_API_ROUTES:
            self.repository.upsert_route(values)
            route_count += 1
        return {"providers": provider_count, "routes": route_count}

    @staticmethod
    def _with_runtime_enabled(values: dict, settings) -> dict:
        result = dict(values)
        provider_code = str(result.get("provider_code") or "")
        runtime_flags = {
            "mimo_2_5": settings.MIMO_ENABLED,
            "cloud_openai": settings.CLOUD_LLM_ENABLED,
            "cloud_openai_vision": settings.CLOUD_VISION_ENABLED,
            "local_llama_cpp": settings.LOCAL_LLM_ENABLED,
            "tesseract_ocr": settings.OCR_ENABLED,
            "custom_ocr_api": settings.OCR_API_ENABLED,
        }
        if provider_code in runtime_flags:
            result["enabled"] = bool(runtime_flags[provider_code])
            if result["enabled"] and result.get("status") in {"disabled", "not_configured", "blocked"}:
                result["status"] = "blocked"
        return result
