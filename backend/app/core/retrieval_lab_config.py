from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class RetrievalLabSettings(BaseSettings):
    """Optional research-only configuration kept outside production settings."""

    ENABLE_RETRIEVAL_LAB: bool = False

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_retrieval_lab_settings() -> RetrievalLabSettings:
    return RetrievalLabSettings()
