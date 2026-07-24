from __future__ import annotations

from pydantic import Field


class VectorSettings:
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_RERANK_ENABLED: bool = False
    DASHSCOPE_RERANK_MODEL: str = "qwen3-rerank"
    DASHSCOPE_RERANK_BASE_URL: str = ""
    DASHSCOPE_RERANK_ENDPOINT: str = "/reranks"
    DASHSCOPE_RERANK_TIMEOUT_SECONDS: float = Field(
        default=3.0,
        gt=0.0,
        le=30.0,
    )
    DASHSCOPE_RERANK_MAX_DOCUMENTS: int = Field(
        default=40,
        ge=20,
        le=50,
    )
    DASHSCOPE_RERANK_TOP_N: int = Field(default=40, ge=1, le=50)
    DASHSCOPE_RERANK_CACHE_ENABLED: bool = True
    DASHSCOPE_RERANK_CACHE_TTL_SECONDS: int = Field(
        default=900,
        ge=1,
        le=86400,
    )
    DASHSCOPE_RERANK_CACHE_MAX_ENTRIES: int = Field(
        default=256,
        ge=1,
        le=4096,
    )
    DASHSCOPE_RERANK_CIRCUIT_FAILURE_THRESHOLD: int = Field(
        default=3,
        ge=1,
        le=20,
    )
    DASHSCOPE_RERANK_CIRCUIT_COOLDOWN_SECONDS: int = Field(
        default=60,
        ge=1,
        le=3600,
    )
    RAG_DEDICATED_RERANK_ENABLED: bool = False
    RAG_DEDICATED_RERANK_PROVIDER: str = "dashscope"
    RAG_DEDICATED_RERANK_MODEL: str = "qwen3-rerank"

    VECTOR_SEARCH_ENABLED: bool = True
    VECTOR_BACKEND: str = "dashvector"
    VECTOR_TOP_K: int = 8
    VECTOR_MIN_SCORE: float = 0.25
    VECTOR_DISTANCE: str = "cosine"

    DASHVECTOR_ENABLED: bool = False
    DASHVECTOR_ENDPOINT: str = (
        "https://vrs-cn-2r34utrl60002l.dashvector.cn-beijing.aliyuncs.com"
    )
    DASHVECTOR_API_KEY: str = ""
    DASHVECTOR_COLLECTION: str = "energy_maintenance_knowledge_te_v4_1024_v1"
    DASHVECTOR_MEDIA_COLLECTION: str = (
        "energy_maintenance_media_te_v4_1024_v1"
    )
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
