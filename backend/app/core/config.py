from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Energy-Maintenance"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    SECRET_KEY: str = "change-this-secret-in-production"
    ADMIN_PASSWORD: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://energy_user:energy_password@127.0.0.1:5432/energy_maintenance"
    )
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=1, ge=0, le=10)
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)

    UPLOAD_DIR: str = "storage/uploads"
    MEDIA_PROCESSED_DIR: str = "storage/processed-media"
    TEMP_DIR: str = ".runtime/tmp"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_DOCUMENT_EXTENSIONS: str = "txt,md,pdf,docx"

    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 150
    LOG_DIR: str = ".runtime/logs"

    KNOWLEDGE_PRIMARY_LANGUAGE: str = "zh-CN"
    KNOWLEDGE_ALLOW_ENGLISH_RETRIEVAL: bool = False
    KNOWLEDGE_ALLOW_ENGLISH_PILOT: bool = False
    KNOWLEDGE_KEEP_ALTERNATE_LANGUAGE: bool = True
    KNOWLEDGE_PREFER_CHINESE_DUPLICATE: bool = True

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

    OCR_ENABLED: bool = False
    OCR_PROVIDER: str = "tesseract"
    OCR_LANG: str = "chi_sim+eng"
    OCR_TIMEOUT_SECONDS: int = 30
    OCR_MAX_IMAGE_MB: int = 10
    OCR_TESSERACT_CMD: str = "tesseract"

    # Task 25C multimodal maintenance safety boundary. Real providers remain
    # opt-in and are additionally gated by the existing provider flags.
    TASK25C_ALLOW_REAL_API: bool = False
    MULTIMODAL_MAX_IMAGE_PIXELS: int = Field(default=40_000_000, ge=1_000_000, le=100_000_000)
    MULTIMODAL_PREPROCESS_MAX_EDGE: int = Field(default=2400, ge=640, le=8192)
    MULTIMODAL_MAX_MEDIA_PER_CASE: int = Field(default=10, ge=1, le=20)
    MULTIMODAL_OCR_MIN_CONFIDENCE: float = Field(default=0.75, ge=0.0, le=1.0)
    MULTIMODAL_VISION_MIN_CONFIDENCE: float = Field(default=0.70, ge=0.0, le=1.0)
    MULTIMODAL_CONFIRMED_MIN_CONFIDENCE: float = Field(default=0.85, ge=0.0, le=1.0)

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
    QUERY_UNDERSTANDING_TIMEOUT_SECONDS: float = 8.0
    RERANK_TIMEOUT_SECONDS: float = 10.0

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

    RAG_QUERY_UNDERSTANDING_PROVIDER: str = "minimax"
    RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL: str = "deterministic"
    RAG_QUERY_UNDERSTANDING_SCHEMA_VERSION: str = "query_understanding_v2"
    RAG_QUERY_UNDERSTANDING_PROMPT_VERSION: str = "task25b_r3_dev_r5_r3_mm_v2"
    RAG_QUERY_UNDERSTANDING_TOTAL_BUDGET_SECONDS: float = 4.0
    RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED: bool = False
    RAG_MINIMAX_AMBIGUITY_MODEL: str = "MiniMax-M3"
    RAG_MINIMAX_AMBIGUITY_PROMPT_VERSION: str = "task25b_r3_dev_r5_r4_mm_v1"
    RAG_MINIMAX_AMBIGUITY_TOTAL_BUDGET_SECONDS: float = 5.0
    RAG_MINIMAX_AMBIGUITY_MAX_TOKENS: int = 160
    RAG_TIEBREAK_PROVIDER: str = "minimax"
    RAG_DETERMINISTIC_RERANK_ENABLED: bool = True
    RAG_OPTIONAL_LLM_TIEBREAK_ENABLED: bool = False
    RAG_TIEBREAK_EXPERIMENTAL_ENABLED: bool = False
    RAG_REQUEST_LEVEL_PROVIDER_FALLBACK_ENABLED: bool = False
    RAG_QUERY_WEIGHT_ORIGINAL: float = 1.0
    RAG_QUERY_WEIGHT_CANONICAL: float = 0.95
    RAG_QUERY_WEIGHT_INTENT: float = 0.86
    RAG_QUERY_WEIGHT_CONDITION: float = 0.82
    RAG_PERFORMANCE_TRACE_ENABLED: bool = True
    RAG_DETAILED_SQL_TRACE_ENABLED: bool = False
    RAG_MAX_CHANNEL_CONCURRENCY: int = Field(default=3, ge=1, le=8)
    RAG_MAX_VECTOR_CONCURRENCY: int = Field(default=3, ge=1, le=8)
    RAG_MAX_QUERY_VARIANT_CONCURRENCY: int = Field(default=3, ge=1, le=8)
    RAG_SCOPE_BATCH_HYDRATION_ENABLED: bool = True
    RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS: float = Field(default=300.0, ge=0.0, le=3600.0)
    RAG_QUERY_RESULT_CACHE_ENABLED: bool = False
    DETERMINISTIC_RERANK_WEIGHTS_VERSION: str = "task25b_r3_dev_r5_r2_mm_v1"
    DETERMINISTIC_RERANK_NORMALIZED_RRF_WEIGHT: float = 0.25
    DETERMINISTIC_RERANK_INTENT_WEIGHT: float = 0.16
    DETERMINISTIC_RERANK_EXACT_MODEL_WEIGHT: float = 0.12
    DETERMINISTIC_RERANK_EXACT_ALARM_WEIGHT: float = 0.12
    DETERMINISTIC_RERANK_SEMANTIC_WEIGHT: float = 0.10
    DETERMINISTIC_RERANK_KEYWORD_WEIGHT: float = 0.07
    DETERMINISTIC_RERANK_VECTOR_WEIGHT: float = 0.06
    DETERMINISTIC_RERANK_CONDITION_WEIGHT: float = 0.04
    DETERMINISTIC_RERANK_CITATION_WEIGHT: float = 0.04
    DETERMINISTIC_RERANK_SOURCE_WEIGHT: float = 0.04
    MINIMAX_TIEBREAK_RELATIVE_MARGIN: float = 0.08

    # Dedicated second-stage passage reranking. The workspace-scoped Base URL
    # is intentionally empty: it must be supplied explicitly and is never
    # inferred from an embedding, model-gateway, or another workspace URL.
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_RERANK_ENABLED: bool = False
    DASHSCOPE_RERANK_MODEL: str = "qwen3-rerank"
    DASHSCOPE_RERANK_BASE_URL: str = ""
    DASHSCOPE_RERANK_ENDPOINT: str = "/reranks"
    DASHSCOPE_RERANK_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0.0, le=30.0)
    DASHSCOPE_RERANK_MAX_DOCUMENTS: int = Field(default=40, ge=20, le=50)
    DASHSCOPE_RERANK_TOP_N: int = Field(default=40, ge=1, le=50)
    DASHSCOPE_RERANK_CACHE_ENABLED: bool = True
    DASHSCOPE_RERANK_CACHE_TTL_SECONDS: int = Field(default=900, ge=1, le=86400)
    DASHSCOPE_RERANK_CACHE_MAX_ENTRIES: int = Field(default=256, ge=1, le=4096)
    DASHSCOPE_RERANK_CIRCUIT_FAILURE_THRESHOLD: int = Field(default=3, ge=1, le=20)
    DASHSCOPE_RERANK_CIRCUIT_COOLDOWN_SECONDS: int = Field(default=60, ge=1, le=3600)
    RAG_DEDICATED_RERANK_ENABLED: bool = False
    RAG_DEDICATED_RERANK_PROVIDER: str = "dashscope"
    RAG_DEDICATED_RERANK_MODEL: str = "qwen3-rerank"

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

    VECTOR_SEARCH_ENABLED: bool = True
    VECTOR_BACKEND: str = "dashvector"
    VECTOR_TOP_K: int = 8
    VECTOR_MIN_SCORE: float = 0.25
    VECTOR_DISTANCE: str = "cosine"

    DASHVECTOR_ENABLED: bool = False
    DASHVECTOR_ENDPOINT: str = "https://vrs-cn-2r34utrl60002l.dashvector.cn-beijing.aliyuncs.com"
    DASHVECTOR_API_KEY: str = ""
    DASHVECTOR_COLLECTION: str = "energy_maintenance_knowledge_te_v4_1024_v1"
    DASHVECTOR_MEDIA_COLLECTION: str = "energy_maintenance_media_te_v4_1024_v1"
    # DashVector enforces a 32-character collection-name limit. The long names
    # remain logical version identifiers; these are provider-safe physical names.
    DASHVECTOR_PHYSICAL_COLLECTION: str = "energy_kn_te_v4_1024_v1"
    DASHVECTOR_PHYSICAL_MEDIA_COLLECTION: str = "energy_media_te_v4_1024_v1"
    DASHVECTOR_R1_CANARY_COLLECTION: str = "energy_kn_te_v4_1024_r1"
    DASHVECTOR_R1_CANARY_MEDIA_COLLECTION: str = "energy_media_te_v4_1024_r1"
    DASHVECTOR_NAMESPACE: str = "default"
    DASHVECTOR_TIMEOUT_SECONDS: int = 60
    DASHVECTOR_CREATE_COLLECTION_IF_NOT_EXISTS: bool = True
    DASHVECTOR_DIMENSION: int = 0
    DASHVECTOR_METRIC: str = "cosine"
    DASHVECTOR_DTYPE: str = "float"
    DASHVECTOR_UPSERT_BATCH_SIZE: int = 50
    DASHVECTOR_QUERY_TOP_K: int = 30
    DASHVECTOR_REAL_CALL_ENABLED: bool = False
    DASHVECTOR_USE_PARTITIONS: bool = True
    DASHVECTOR_BASE_PARTITION: str = ""
    DASHVECTOR_PILOT_PARTITION: str = "pilot_r2"
    DASHVECTOR_CREATE_PARTITION_IF_NOT_EXISTS: bool = True

    HYBRID_RETRIEVAL_ENABLED: bool = True
    HYBRID_KEYWORD_WEIGHT: float = 0.35
    HYBRID_VECTOR_WEIGHT: float = 0.65
    HYBRID_MIN_SCORE: float = 0.20
    RETRIEVAL_DEFAULT_MODE: str = "keyword"
    RETRIEVAL_VECTOR_MIN_USEFUL_SCORE: float = 0.76
    RETRIEVAL_RRF_K: int = 60
    RETRIEVAL_TOTAL_BUDGET_MS: int = 3500
    RETRIEVAL_VECTOR_TIMEOUT_SECONDS: float = 3.5
    RETRIEVAL_ABSTENTION_MIN_SCORE: float = 0.35
    RETRIEVAL_ABSTENTION_MIN_MARGIN: float = 0.02
    RETRIEVAL_QUALITY_GATE_STATUS: str = "PASSED_CONTROLLED_TEST_V2"

    EMBEDDING_ENABLED: bool = False
    EMBEDDING_PROVIDER: str = "openai_compatible"
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_DIM: int = 0
    EMBEDDING_API_TYPE: str = "openai_compatible"
    EMBEDDING_EMBEDDINGS_PATH: str = "/embeddings"
    EMBEDDING_ENCODING_FORMAT: str = "float"
    EMBEDDING_BATCH_SIZE: int = 10
    EMBEDDING_MAX_INPUT_TOKENS: int = 8192
    EMBEDDING_TIMEOUT_SECONDS: int = 60
    EMBEDDING_MAX_RETRIES: int = 4
    EMBEDDING_RETRY_BASE_SECONDS: float = 1.0
    EMBEDDING_REAL_CALL_ENABLED: bool = False
    EMBEDDING_INDEX_VERSION: str = "text-embedding-v4-1024-v1"
    EMBEDDING_QUERY_CACHE_TTL_SECONDS: int = 300
    EMBEDDING_QUERY_CACHE_MAX_ENTRIES: int = 512
    EMBEDDING_MAX_CONCURRENCY: int = 2

    TASK25B_ALLOW_REAL_API: bool = False
    TASK25B_ALLOW_FULL_REINDEX: bool = False
    TASK25B_R2_PILOT_ENABLED: bool = False
    TASK25B_R2_ALLOW_PILOT_INDEX: bool = False
    TASK25B_R2_ALLOW_PILOT_SWITCH: bool = False
    TASK25B_R2_ALLOW_PILOT_ROLLBACK: bool = False
    DASHVECTOR_PILOT_COLLECTION: str = "energy_kn_te_v4_1024_pilot1"
    DASHVECTOR_PILOT_MEDIA_COLLECTION: str = "energy_media_te_v4_1024_pilot1"
    RETRIEVAL_PILOT_MODE: str = "adaptive_conservative"

    EMBEDDING_TEST_PROVIDER_ENABLED: bool = True
    EMBEDDING_TEST_DIM: int = 384

    RERANK_ENABLED: bool = False
    RERANK_PROVIDER: str = "openai_compatible"
    RERANK_BASE_URL: str = ""
    RERANK_API_KEY: str = ""
    RERANK_MODEL: str = ""
    RERANK_TOP_K: int = 5
    RETRIEVAL_FEATURE_RERANK_ENABLED: bool = False

    SECURITY_REQUIRE_STRONG_PRODUCTION_CONFIG: bool = True
    SECURITY_MIN_SECRET_KEY_LENGTH: int = 32
    SECURITY_MIN_ADMIN_PASSWORD_LENGTH: int = 10
    SECURITY_MAX_REQUEST_BODY_MB: int = 20
    SECURITY_MAX_JSON_BODY_MB: int = 5

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_EXEMPT_PATHS: str = "/api/health,/api/system/status,/docs,/openapi.json"

    CORS_ALLOWED_ORIGINS: str = "http://127.0.0.1:8010,http://localhost:8010,http://127.0.0.1:5173,http://localhost:5173"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Authorization,Content-Type"

    SECURITY_SCAN_EXCLUDE_DIRS: str = "node_modules,.venv,dist,backend/static/frontend/assets,delivery,delivery_staging,.git"
    SECURITY_SCAN_ALLOW_ENV_FILE: bool = True

    EXTERNAL_REAL_CALLS_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def allowed_document_extensions(self) -> list[str]:
        return [
            extension.strip().lower()
            for extension in self.ALLOWED_DOCUMENT_EXTENSIONS.split(",")
            if extension.strip()
        ]

    @property
    def cors_allowed_origins(self) -> list[str]:
        return self._csv_values(self.CORS_ALLOWED_ORIGINS)

    @property
    def cors_allow_methods(self) -> list[str]:
        return self._csv_values(self.CORS_ALLOW_METHODS)

    @property
    def cors_allow_headers(self) -> list[str]:
        return self._csv_values(self.CORS_ALLOW_HEADERS)

    @property
    def rate_limit_exempt_paths(self) -> list[str]:
        return self._csv_values(self.RATE_LIMIT_EXEMPT_PATHS)

    @property
    def security_scan_exclude_dirs(self) -> list[str]:
        return self._csv_values(self.SECURITY_SCAN_EXCLUDE_DIRS)

    @staticmethod
    def _csv_values(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.APP_ENV.strip().lower() == "production" and self.SECRET_KEY == "change-this-secret-in-production":
            raise ValueError("SECRET_KEY must be replaced before production startup")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
