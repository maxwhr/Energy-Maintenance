from __future__ import annotations


class ProviderSettings:
    MODEL_GATEWAY_DEFAULT_PROVIDER: str = "rule_based"
    MODEL_GATEWAY_TIMEOUT_SECONDS: int = 20
    MODEL_GATEWAY_ENABLE_LOGGING: bool = True
    MODEL_GATEWAY_ALLOW_FALLBACK: bool = True

    LOCAL_LLM_ENABLED: bool = False
    LOCAL_LLM_BASE_URL: str = "http://127.0.0.1:8080"
    LOCAL_LLM_MODEL: str = "local-gguf-model"
    LOCAL_LLM_API_TYPE: str = "openai_compatible"
    LOCAL_LLM_TIMEOUT_SECONDS: int = 60
    LOCAL_LLM_MAX_TOKENS: int = 1024
    LOCAL_LLM_TEMPERATURE: float = 0.2
    LOCAL_LLM_HEALTH_PATH: str = "/health"
    LOCAL_LLM_NATIVE_COMPLETION_PATH: str = "/completion"
    LOCAL_LLM_OPENAI_CHAT_PATH: str = "/v1/chat/completions"

    CLOUD_LLM_ENABLED: bool = False
    CLOUD_LLM_BASE_URL: str = ""
    CLOUD_LLM_API_KEY: str = ""
    CLOUD_LLM_MODEL: str = ""
    CLOUD_LLM_API_TYPE: str = "openai_compatible"
    CLOUD_LLM_TIMEOUT_SECONDS: int = 60
    CLOUD_LLM_MAX_TOKENS: int = 1024
    CLOUD_LLM_TEMPERATURE: float = 0.2
    STRUCTURED_OUTPUT_MODE: str = "auto"
    STRUCTURED_OUTPUT_PROBE_ENABLED: bool = True

    MINIMAX_ENABLED: bool = False
    MINIMAX_API_KEY: str = ""
    MINIMAX_PROTOCOL: str = "anthropic"
    MINIMAX_ANTHROPIC_BASE_URL: str = "https://api.minimaxi.com/anthropic"
    MINIMAX_OPENAI_BASE_URL: str = "https://api.minimaxi.com/v1"
    MINIMAX_MODEL: str = "MiniMax-M3"
    MINIMAX_QUERY_UNDERSTANDING_MODEL: str = "MiniMax-M3"
    MINIMAX_TIEBREAK_MODEL: str = "MiniMax-M3"
    MINIMAX_THINKING_TYPE: str = "disabled"
    MINIMAX_TOOL_CALL_ENABLED: bool = True
    MINIMAX_FORCE_TOOL_CHOICE: bool = True
    MINIMAX_SERVICE_TIER: str = "standard"
    MINIMAX_TEMPERATURE: float = 0.0
    MINIMAX_TOP_P: float = 0.9
    MINIMAX_QUERY_MAX_TOKENS: int = 1024
    MINIMAX_TIEBREAK_MAX_TOKENS: int = 768
    MINIMAX_QUERY_TIMEOUT_SECONDS: float = 8.0
    MINIMAX_TIEBREAK_TIMEOUT_SECONDS: float = 7.0
    MINIMAX_MAX_RETRIES: int = 0
    MINIMAX_MAX_TIEBREAK_CANDIDATES: int = 6
    MINIMAX_CACHE_TTL_SECONDS: int = 900
    MINIMAX_CACHE_MAX_ENTRIES: int = 256
    MINIMAX_CIRCUIT_COOLDOWN_SECONDS: int = 60

    MIMO_ENABLED: bool = False
    MIMO_BASE_URL: str = ""
    MIMO_API_KEY: str = ""
    MIMO_MODEL: str = "mimo-2.5"
    MIMO_API_PROFILE: str = "openai_compatible_vision"
    MIMO_TIMEOUT_SECONDS: int = 60
    MIMO_MAX_TOKENS: int = 2048
    MIMO_TEMPERATURE: float = 0.1

    CLOUD_VISION_ENABLED: bool = False
    CLOUD_VISION_BASE_URL: str = ""
    CLOUD_VISION_API_KEY: str = ""
    CLOUD_VISION_MODEL: str = ""

    OCR_API_ENABLED: bool = False
    OCR_API_BASE_URL: str = ""
    OCR_API_KEY: str = ""
    OCR_API_MODEL: str = ""

    EXTERNAL_REAL_CALLS_ENABLED: bool = False
