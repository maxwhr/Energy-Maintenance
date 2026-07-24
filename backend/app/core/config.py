from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.settings import (
    ApplicationSettings,
    DatabaseSettings,
    KnowledgeSettings,
    MultimodalSettings,
    ProviderSettings,
    RetrievalSettings,
    SecuritySettings,
    SettingsValidation,
    StorageSettings,
    VectorSettings,
)


class Settings(
    SettingsValidation,
    SecuritySettings,
    MultimodalSettings,
    ProviderSettings,
    VectorSettings,
    RetrievalSettings,
    KnowledgeSettings,
    StorageSettings,
    DatabaseSettings,
    ApplicationSettings,
    BaseSettings,
):
    """Flat, environment-compatible settings assembled from domain groups."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
