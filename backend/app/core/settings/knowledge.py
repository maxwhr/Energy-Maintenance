from __future__ import annotations


class KnowledgeSettings:
    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 150

    KNOWLEDGE_PRIMARY_LANGUAGE: str = "zh-CN"
    KNOWLEDGE_ALLOW_ENGLISH_RETRIEVAL: bool = False
    KNOWLEDGE_ALLOW_ENGLISH_PILOT: bool = False
    KNOWLEDGE_KEEP_ALTERNATE_LANGUAGE: bool = True
    KNOWLEDGE_PREFER_CHINESE_DUPLICATE: bool = True
