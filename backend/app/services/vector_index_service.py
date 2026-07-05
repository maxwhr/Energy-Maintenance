from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument, User, VectorIndexRun
from app.repositories.vector_index_repository import VectorIndexRepository
from app.schemas.vector_index import (
    ChunkVectorIndexRead,
    DocumentVectorIndexStatus,
    VectorIndexJobResponse,
    VectorIndexRunRead,
    VectorSearchStatus,
    VectorTestQueryHit,
    VectorTestQueryResponse,
)
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
from app.services.vector_store_adapters import (
    DashVectorAdapter,
    FakeInMemoryVectorAdapter,
    VectorRecord,
    VectorSearchHit,
    VectorStoreAdapterError,
)


class VectorIndexServiceError(ValueError):
    pass


@dataclass(slots=True)
class VerifiedVectorHit:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
    vector_id: str | None
    metadata: dict


class VectorIndexService:
    def __init__(self, db: Session, *, allow_real_api: bool = False):
        self.db = db
        self.settings = get_settings()
        self.repository = VectorIndexRepository(db)
        self.embedding_service = EmbeddingService(allow_real_api=allow_real_api)
        self.allow_real_api = allow_real_api

    def status(self) -> VectorSearchStatus:
        real_dashvector_configured = bool(
            self.settings.DASHVECTOR_ENDPOINT
            and self.settings.DASHVECTOR_API_KEY
            and self.settings.DASHVECTOR_COLLECTION
            and self.settings.DASHVECTOR_DIMENSION > 0
        )
        real_embedding_configured = bool(
            self.settings.EMBEDDING_BASE_URL
            and self.settings.EMBEDDING_API_KEY
            and self.settings.EMBEDDING_MODEL
            and self.settings.EMBEDDING_DIM > 0
        )
        blocked_reasons: list[str] = []
        warnings: list[str] = []
        if self.settings.VECTOR_BACKEND != "dashvector":
            blocked_reasons.append("VECTOR_BACKEND must be dashvector for the selected 24B route")
        if not self.settings.DASHVECTOR_ENABLED:
            blocked_reasons.append("DASHVECTOR_ENABLED=false; real DashVector calls are disabled")
        elif not real_dashvector_configured:
            blocked_reasons.append("DASHVECTOR_ENABLED=true but DashVector config is incomplete")
        if not self.settings.EMBEDDING_ENABLED:
            blocked_reasons.append("EMBEDDING_ENABLED=false; real embedding API is disabled")
        elif not real_embedding_configured:
            blocked_reasons.append("EMBEDDING_ENABLED=true but embedding config is incomplete")
        if (
            self.settings.DASHVECTOR_ENABLED
            and self.settings.EMBEDDING_ENABLED
            and self.settings.DASHVECTOR_DIMENSION
            and self.settings.EMBEDDING_DIM
            and self.settings.DASHVECTOR_DIMENSION != self.settings.EMBEDDING_DIM
        ):
            blocked_reasons.append("DASHVECTOR_DIMENSION must equal EMBEDDING_DIM")
        if self.settings.EMBEDDING_TEST_PROVIDER_ENABLED:
            warnings.append("deterministic_test embedding is for local repeatable tests only")
        warnings.append("fake_in_memory vector adapter is local test mode and is not real DashVector")
        return VectorSearchStatus(
            vector_search_enabled=self.settings.VECTOR_SEARCH_ENABLED,
            vector_backend=self.settings.VECTOR_BACKEND,
            dashvector_enabled=self.settings.DASHVECTOR_ENABLED,
            dashvector_configured=real_dashvector_configured,
            dashvector_collection=self.settings.DASHVECTOR_COLLECTION,
            dashvector_namespace=self.settings.DASHVECTOR_NAMESPACE,
            dashvector_dimension=self.settings.DASHVECTOR_DIMENSION,
            embedding_enabled=self.settings.EMBEDDING_ENABLED,
            embedding_configured=real_embedding_configured,
            embedding_provider=self.settings.EMBEDDING_PROVIDER,
            embedding_model=self.settings.EMBEDDING_MODEL or None,
            embedding_dimension=self.settings.EMBEDDING_DIM,
            deterministic_test_enabled=self.settings.EMBEDDING_TEST_PROVIDER_ENABLED,
            fake_adapter_available=True,
            real_adapter_available=real_dashvector_configured and real_embedding_configured,
            status="blocked" if blocked_reasons else "available",
            blocked_reasons=blocked_reasons,
            warnings=warnings,
        )

    def list_runs(self, *, page: int = 1, page_size: int = 20) -> dict:
        runs, total = self.repository.list_runs(page=page, page_size=page_size)
        return {
            "items": [VectorIndexRunRead.model_validate(run).model_dump(mode="json") for run in runs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_run(self, run_id: UUID) -> VectorIndexRun | None:
        return self.repository.get_run(run_id)

    def document_status(self, document_id: UUID) -> DocumentVectorIndexStatus:
        indexes = self.repository.list_indexes_by_document(document_id)
        indexed = [item for item in indexes if item.index_status == "active"]
        failed = [item for item in indexes if item.index_status == "failed"]
        stale = [item for item in indexes if item.index_status == "stale"]
        return DocumentVectorIndexStatus(
            document_id=document_id,
            chunk_count=len({item.chunk_id for item in indexes}),
            indexed_count=len(indexed),
            stale_count=len(stale),
            failed_count=len(failed),
            indexes=[ChunkVectorIndexRead.model_validate(item) for item in indexes],
        )

    def chunk_status(self, chunk_id: UUID) -> list[ChunkVectorIndexRead]:
        return [ChunkVectorIndexRead.model_validate(item) for item in self.repository.list_indexes_by_chunk(chunk_id)]

    def index_document(
        self,
        document_id: UUID,
        *,
        current_user: User,
        provider: str | None = None,
        vector_backend: str | None = None,
        force: bool = False,
    ) -> VectorIndexJobResponse:
        chunks = self.repository.list_chunks_for_document(document_id)
        if not chunks:
            raise VectorIndexServiceError("No parsed active chunks found for document")
        return self._index_chunks(
            chunks,
            run_type="document_index",
            target_type="document",
            target_id=document_id,
            current_user=current_user,
            provider=provider,
            vector_backend=vector_backend,
            force=force,
        )

    def index_chunk(
        self,
        chunk_id: UUID,
        *,
        current_user: User,
        provider: str | None = None,
        vector_backend: str | None = None,
        force: bool = False,
    ) -> VectorIndexJobResponse:
        item = self.repository.get_chunk_with_document(chunk_id)
        if not item:
            raise VectorIndexServiceError("Knowledge chunk not found")
        return self._index_chunks(
            [item],
            run_type="chunk_index",
            target_type="chunk",
            target_id=chunk_id,
            current_user=current_user,
            provider=provider,
            vector_backend=vector_backend,
            force=force,
        )

    def reindex_stale(
        self,
        *,
        current_user: User,
        provider: str | None = None,
        vector_backend: str | None = None,
        limit: int = 200,
    ) -> VectorIndexJobResponse:
        config = self._runtime_config(provider=provider, vector_backend=vector_backend)
        chunks = self.repository.list_stale_chunks(
            vector_backend=config["vector_backend"],
            collection_name=config["collection_name"],
            namespace=config["namespace"],
            embedding_model=config["embedding_model"],
            embedding_provider=config["embedding_provider"],
            limit=limit,
        )
        return self._index_chunks(
            chunks,
            run_type="reindex_stale",
            target_type="all",
            target_id=None,
            current_user=current_user,
            provider=provider,
            vector_backend=vector_backend,
            force=False,
        )

    def test_query(
        self,
        text: str,
        *,
        provider: str | None = None,
        vector_backend: str | None = None,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> VectorTestQueryResponse:
        hits, diagnostics = self.search(text, provider=provider, vector_backend=vector_backend, top_k=top_k, filters=filters)
        return VectorTestQueryResponse(
            vector_backend=diagnostics["vector_backend"],
            embedding_provider=diagnostics["embedding_provider"],
            embedding_model=diagnostics["embedding_model"],
            embedding_dimension=diagnostics["embedding_dimension"],
            vector_available=diagnostics["vector_available"],
            hits=[
                VectorTestQueryHit(
                    chunk_id=hit.chunk.id,
                    document_id=hit.document.id,
                    document_title=hit.document.title,
                    chunk_index=hit.chunk.chunk_index,
                    section_title=hit.chunk.section_title,
                    vector_score=hit.score,
                    vector_backend=diagnostics["vector_backend"],
                    vector_id=hit.vector_id,
                    metadata={**hit.metadata, "raw_vector_returned": False},
                )
                for hit in hits
            ],
            warnings=diagnostics.get("warnings", []),
        )

    def search(
        self,
        text: str,
        *,
        provider: str | None = None,
        vector_backend: str | None = None,
        top_k: int = 8,
        filters: dict | None = None,
    ) -> tuple[list[VerifiedVectorHit], dict]:
        if not self.settings.VECTOR_SEARCH_ENABLED:
            return [], self._diagnostics(vector_available=False, fallback_reason="vector search disabled")
        config = self._runtime_config(provider=provider, vector_backend=vector_backend)
        try:
            embedding = self.embedding_service.embed_text(text, provider=config["embedding_provider"])
            adapter = self._adapter(config)
            raw_hits = adapter.query_vectors(vector=embedding.vectors[0], top_k=top_k, filters=filters)
        except (EmbeddingServiceError, VectorStoreAdapterError) as exc:
            return [], self._diagnostics(config=config, vector_available=False, fallback_reason=str(exc))
        chunk_ids = [self._metadata_uuid(hit, "chunk_id") for hit in raw_hits]
        chunk_ids = [item for item in chunk_ids if item]
        verified = self.repository.approved_active_chunks_by_ids(
            chunk_ids,
            manufacturer=(filters or {}).get("manufacturer"),
            product_series=(filters or {}).get("product_series"),
            device_type=(filters or {}).get("device_type") or "pv_inverter",
            document_type=(filters or {}).get("document_type"),
        )
        result: list[VerifiedVectorHit] = []
        for hit in raw_hits:
            chunk_id = self._metadata_uuid(hit, "chunk_id")
            if not chunk_id or chunk_id not in verified or hit.score < self.settings.VECTOR_MIN_SCORE:
                continue
            chunk, document = verified[chunk_id]
            result.append(
                VerifiedVectorHit(
                    chunk=chunk,
                    document=document,
                    score=hit.score,
                    vector_id=hit.vector_id,
                    metadata=hit.metadata,
                )
            )
        return result, self._diagnostics(config=config, vector_available=True, raw_hits=len(raw_hits), verified_hits=len(result))

    def _index_chunks(
        self,
        chunks: list[tuple[KnowledgeChunk, KnowledgeDocument]],
        *,
        run_type: str,
        target_type: str,
        target_id: UUID | None,
        current_user: User,
        provider: str | None,
        vector_backend: str | None,
        force: bool,
    ) -> VectorIndexJobResponse:
        config = self._runtime_config(provider=provider, vector_backend=vector_backend)
        run = VectorIndexRun(
            run_type=run_type,
            target_type=target_type,
            target_id=target_id,
            vector_backend=config["vector_backend"],
            collection_name=config["collection_name"],
            namespace=config["namespace"],
            embedding_model=config["embedding_model"],
            embedding_provider=config["embedding_provider"],
            status="running",
            total_count=len(chunks),
            started_at=datetime.now(timezone.utc),
            created_by=current_user.id,
            metadata_json={"force": force, "external_api_called": self.allow_real_api},
        )
        warnings: list[str] = []
        try:
            run = self.repository.create_run(run)
            adapter = self._adapter(config)
            adapter.ensure_collection(dimension=config["embedding_dim"])
            succeeded = skipped = failed = 0
            records: list[VectorRecord] = []
            record_context: list[tuple[KnowledgeChunk, KnowledgeDocument, str]] = []
            for chunk, document in chunks:
                content_hash = chunk.content_hash or EmbeddingService.content_hash(chunk.content)
                existing = self.repository.get_index_for_chunk(
                    chunk.id,
                    vector_backend=config["vector_backend"],
                    collection_name=config["collection_name"],
                    namespace=config["namespace"],
                    embedding_model=config["embedding_model"],
                    embedding_provider=config["embedding_provider"],
                )
                if existing and existing.index_status == "active" and existing.content_hash == content_hash and not force:
                    skipped += 1
                    continue
                try:
                    embedding = self.embedding_service.embed_text(chunk.content, provider=config["embedding_provider"])
                    vector_id = self._vector_id(chunk.id, config)
                    metadata = self._vector_metadata(chunk, document, config, content_hash)
                    records.append(VectorRecord(vector_id=vector_id, vector=embedding.vectors[0], metadata=metadata))
                    record_context.append((chunk, document, content_hash))
                except EmbeddingServiceError as exc:
                    failed += 1
                    self.repository.mark_index_failed(
                        chunk=chunk,
                        document=document,
                        vector_backend=config["vector_backend"],
                        collection_name=config["collection_name"],
                        namespace=config["namespace"],
                        embedding_model=config["embedding_model"],
                        embedding_provider=config["embedding_provider"],
                        content_hash=content_hash,
                        error_message=str(exc),
                    )
            if records:
                adapter.upsert_vectors(records)
            for record, (chunk, document, content_hash) in zip(records, record_context):
                self.repository.upsert_index(
                    chunk=chunk,
                    document=document,
                    vector_backend=config["vector_backend"],
                    collection_name=config["collection_name"],
                    namespace=config["namespace"],
                    vector_id=record.vector_id,
                    embedding_model=config["embedding_model"],
                    embedding_provider=config["embedding_provider"],
                    embedding_dim=config["embedding_dim"],
                    content_hash=content_hash,
                    metadata_json={**record.metadata, "raw_vector_stored_in_postgresql": False},
                )
                succeeded += 1
            run.succeeded_count = succeeded
            run.failed_count = failed
            run.skipped_count = skipped
            run.status = "succeeded" if failed == 0 else "partial_failed"
            run.finished_at = datetime.now(timezone.utc)
            run = self.repository.update_run(run)
            self.db.commit()
        except (SQLAlchemyError, VectorStoreAdapterError, EmbeddingServiceError) as exc:
            self.db.rollback()
            run.status = "failed"
            run.error_message = str(exc)[:1000]
            run.finished_at = datetime.now(timezone.utc)
            self.db.add(run)
            self.db.commit()
            raise VectorIndexServiceError(str(exc)) from exc
        if config["vector_backend"] == "fake_in_memory":
            warnings.append("fake_in_memory vector backend is local test only; it is not real DashVector")
        return VectorIndexJobResponse(
            run=VectorIndexRunRead.model_validate(run),
            processed=len(chunks),
            succeeded=run.succeeded_count,
            skipped=run.skipped_count,
            failed=run.failed_count,
            vector_backend=config["vector_backend"],
            embedding_provider=config["embedding_provider"],
            embedding_model=config["embedding_model"],
            embedding_dimension=config["embedding_dim"],
            warnings=warnings,
        )

    def _runtime_config(self, *, provider: str | None = None, vector_backend: str | None = None) -> dict:
        backend = vector_backend or ("dashvector" if self.settings.DASHVECTOR_ENABLED and self.allow_real_api else "fake_in_memory")
        embedding_provider = provider or (
            self.settings.EMBEDDING_PROVIDER if self.settings.EMBEDDING_ENABLED and self.allow_real_api else "deterministic_test"
        )
        if embedding_provider == "deterministic_test":
            embedding_model = "deterministic_hash_v1"
            embedding_dim = self.settings.EMBEDDING_TEST_DIM
        else:
            embedding_model = self.settings.EMBEDDING_MODEL
            embedding_dim = self.settings.EMBEDDING_DIM
        if backend == "dashvector":
            dimension = self.settings.DASHVECTOR_DIMENSION or embedding_dim
        else:
            dimension = embedding_dim
        return {
            "vector_backend": backend,
            "collection_name": self.settings.DASHVECTOR_COLLECTION,
            "namespace": self.settings.DASHVECTOR_NAMESPACE,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "embedding_dim": int(dimension or embedding_dim or 0),
        }

    def _adapter(self, config: dict):
        if config["vector_backend"] == "fake_in_memory":
            return FakeInMemoryVectorAdapter(
                collection_name=config["collection_name"],
                namespace=config["namespace"],
                dimension=config["embedding_dim"],
            )
        if config["vector_backend"] == "dashvector":
            return DashVectorAdapter(
                endpoint=self.settings.DASHVECTOR_ENDPOINT,
                api_key=self.settings.DASHVECTOR_API_KEY,
                collection_name=config["collection_name"],
                namespace=config["namespace"],
                dimension=config["embedding_dim"],
                metric=self.settings.DASHVECTOR_METRIC,
                timeout_seconds=self.settings.DASHVECTOR_TIMEOUT_SECONDS,
                allow_real_api=self.allow_real_api and self.settings.DASHVECTOR_ENABLED,
            )
        raise VectorIndexServiceError(f"Unsupported vector backend: {config['vector_backend']}")

    @staticmethod
    def _vector_id(chunk_id: UUID, config: dict) -> str:
        return f"{config['collection_name']}:{config['namespace']}:{chunk_id}"

    @staticmethod
    def _vector_metadata(chunk: KnowledgeChunk, document: KnowledgeDocument, config: dict, content_hash: str) -> dict:
        return {
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "document_title": document.title,
            "chunk_index": chunk.chunk_index,
            "manufacturer": document.manufacturer,
            "product_series": document.product_series,
            "device_type": document.device_type,
            "document_type": document.document_type,
            "review_status": document.review_status,
            "parse_status": document.parse_status,
            "status": document.status,
            "content_hash": content_hash,
            "vector_backend": config["vector_backend"],
            "embedding_provider": config["embedding_provider"],
            "embedding_model": config["embedding_model"],
        }

    @staticmethod
    def _metadata_uuid(hit: VectorSearchHit, key: str) -> UUID | None:
        try:
            value = hit.metadata.get(key)
            return UUID(str(value)) if value else None
        except (TypeError, ValueError):
            return None

    def _diagnostics(
        self,
        *,
        config: dict | None = None,
        vector_available: bool,
        fallback_reason: str | None = None,
        raw_hits: int = 0,
        verified_hits: int = 0,
    ) -> dict:
        config = config or self._runtime_config(provider=None, vector_backend=None)
        warnings = []
        if config["vector_backend"] == "fake_in_memory":
            warnings.append("fake_in_memory vector backend is local test only; not real DashVector")
        if config["embedding_provider"] == "deterministic_test":
            warnings.append("deterministic_test embedding is local test only; not production semantic embedding")
        return {
            "vector_backend": config["vector_backend"],
            "embedding_provider": config["embedding_provider"],
            "embedding_model": config["embedding_model"],
            "embedding_dimension": config["embedding_dim"],
            "vector_available": vector_available,
            "fallback_reason": fallback_reason,
            "raw_vector_hits": raw_hits,
            "verified_vector_hits": verified_hits,
            "external_api_called": False,
            "test_backend": config["vector_backend"] == "fake_in_memory",
            "warnings": warnings,
        }
