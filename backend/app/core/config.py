from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Energy-Maintenance"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    SECRET_KEY: str = "change-this-secret-in-production"
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

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if (
            self.APP_ENV.strip().lower() == "production"
            and self.SECRET_KEY == "change-this-secret-in-production"
        ):
            raise ValueError("SECRET_KEY must be replaced before production startup")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
