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

    UPLOAD_DIR: str = "storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_DOCUMENT_EXTENSIONS: str = "txt,md,pdf,docx"

    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 150
    LOG_DIR: str = ".runtime/logs"

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

    CLOUD_LLM_ENABLED: bool = False
    CLOUD_LLM_BASE_URL: str = ""
    CLOUD_LLM_API_KEY: str = ""
    CLOUD_LLM_MODEL: str = ""
    CLOUD_LLM_API_TYPE: str = "openai_compatible"
    CLOUD_LLM_TIMEOUT_SECONDS: int = 60
    CLOUD_LLM_MAX_TOKENS: int = 1024
    CLOUD_LLM_TEMPERATURE: float = 0.2

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
    DASHVECTOR_COLLECTION: str = "energy_maintenance_knowledge"
    DASHVECTOR_NAMESPACE: str = "default"
    DASHVECTOR_TIMEOUT_SECONDS: int = 60
    DASHVECTOR_CREATE_COLLECTION_IF_NOT_EXISTS: bool = True
    DASHVECTOR_DIMENSION: int = 0
    DASHVECTOR_METRIC: str = "cosine"

    HYBRID_RETRIEVAL_ENABLED: bool = True
    HYBRID_KEYWORD_WEIGHT: float = 0.35
    HYBRID_VECTOR_WEIGHT: float = 0.65
    HYBRID_MIN_SCORE: float = 0.20

    EMBEDDING_ENABLED: bool = False
    EMBEDDING_PROVIDER: str = "openai_compatible"
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_DIM: int = 0
    EMBEDDING_API_TYPE: str = "openai_compatible"
    EMBEDDING_EMBEDDINGS_PATH: str = "/embeddings"
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_TIMEOUT_SECONDS: int = 60

    EMBEDDING_TEST_PROVIDER_ENABLED: bool = True
    EMBEDDING_TEST_DIM: int = 384

    RERANK_ENABLED: bool = False
    RERANK_PROVIDER: str = "openai_compatible"
    RERANK_BASE_URL: str = ""
    RERANK_API_KEY: str = ""
    RERANK_MODEL: str = ""
    RERANK_TOP_K: int = 5

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
