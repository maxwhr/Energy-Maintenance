from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings:
    QUERY_UNDERSTANDING_TIMEOUT_SECONDS: float = 8.0
    RERANK_TIMEOUT_SECONDS: float = 10.0

    RAG_QUERY_UNDERSTANDING_PROVIDER: str = "minimax"
    RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL: str = "deterministic"
    RAG_QUERY_UNDERSTANDING_SCHEMA_VERSION: str = "query_understanding_v2"
    RAG_QUERY_UNDERSTANDING_PROMPT_VERSION: str = "task25b_r3_dev_r5_r3_mm_v2"
    RAG_QUERY_UNDERSTANDING_TOTAL_BUDGET_SECONDS: float = 4.0
    RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED: bool = False
    RAG_MINIMAX_AMBIGUITY_MODEL: str = "MiniMax-M3"
    RAG_MINIMAX_AMBIGUITY_PROMPT_VERSION: str = (
        "task25b_r3_dev_r5_r4_mm_v1"
    )
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
    RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS: float = Field(
        default=300.0,
        ge=0.0,
        le=3600.0,
    )
    RAG_QUERY_RESULT_CACHE_ENABLED: bool = False

    DETERMINISTIC_RERANK_WEIGHTS_VERSION: str = (
        "task25b_r3_dev_r5_r2_mm_v1"
    )
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


BACKEND_DIR = Path(__file__).resolve().parents[3]


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
