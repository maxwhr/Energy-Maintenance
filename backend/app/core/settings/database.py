from __future__ import annotations

from pydantic import Field


class DatabaseSettings:
    DATABASE_URL: str = Field(
        default=(
            "postgresql+psycopg://energy_user:energy_password"
            "@127.0.0.1:5432/energy_maintenance"
        )
    )
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=1, ge=0, le=10)
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)
