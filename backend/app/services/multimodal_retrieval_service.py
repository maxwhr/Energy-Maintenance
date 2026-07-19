from __future__ import annotations

import hashlib
import math
import re
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import MediaSimilarityFeature, UploadedMedia
from app.schemas.high_precision_retrieval import (
    MultimodalMatch,
    MultimodalRetrievalResponse,
    MultimodalScoreBreakdown,
)
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
from app.services.media_service import MediaService, MediaServiceError
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.vector_index_service import VectorIndexService
from app.services.vector_store_adapters import DashVectorAdapter, VectorRecord, VectorStoreAdapterError


class MultimodalRetrievalServiceError(ValueError):
    pass


class MultimodalRetrievalService:
    CAPABILITY_LABEL = "descriptor_based_cross_modal"

    def __init__(self, db: Session, *, allow_real_api: bool | None = None):
        self.db = db
        self.settings = get_settings()
        requested = self.settings.TASK25B_ALLOW_REAL_API if allow_real_api is None else allow_real_api
        self.allow_real_api = bool(requested and self.settings.TASK25B_ALLOW_REAL_API)
        self.embedding = EmbeddingService(allow_real_api=self.allow_real_api)
        self.media_service = MediaService(db)
        self.query_understanding = QueryUnderstandingService()

    def retrieve(self, media_id: UUID, *, top_k: int = 5) -> MultimodalRetrievalResponse:
        feature = self.ensure_feature(media_id)
        descriptor = feature.visual_descriptor
        warnings = ["Results are descriptor-based cross-modal matches and require human review."]
        manual_matches = self._knowledge_matches(descriptor, document_type="manual", top_k=top_k)
        case_matches = self._knowledge_matches(descriptor, document_type="fault_case", top_k=top_k)
        similar_media: list[MultimodalMatch] = []
        vector_diagnostics: dict = {"vector_available": False, "external_api_called": False}
        try:
            similar_media, vector_diagnostics = self._similar_media(feature, top_k=top_k)
        except (EmbeddingServiceError, VectorStoreAdapterError) as exc:
            warnings.append(str(exc))
        return MultimodalRetrievalResponse(
            media_id=media_id,
            canonical_descriptor=descriptor,
            descriptor_embedding_model=feature.embedding_model,
            descriptor_embedding_dimension=feature.embedding_dimension,
            manual_matches=manual_matches,
            case_matches=case_matches,
            similar_media=similar_media,
            warnings=warnings,
            diagnostics={
                "capability_label": self.CAPABILITY_LABEL,
                "raw_image_embedding": False,
                "vector_backend": "dashvector" if self.allow_real_api else "unavailable",
                **vector_diagnostics,
            },
        )

    def ensure_feature(self, media_id: UUID) -> MediaSimilarityFeature:
        media = self.db.get(UploadedMedia, media_id)
        if not media or media.status != "active":
            raise MultimodalRetrievalServiceError("Active media item not found")
        descriptor, analysis = self._descriptor(media)
        content_hash = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()
        existing = self.db.scalar(select(MediaSimilarityFeature).where(MediaSimilarityFeature.media_id == media_id))
        if existing and existing.content_hash == content_hash and existing.feature_status == "active":
            return existing
        try:
            path = self.media_service.resolve_file_path(media)
            phash, dhash, hash_method = self._image_hashes(path, media.metadata_json or {})
        except MediaServiceError as exc:
            raise MultimodalRetrievalServiceError(str(exc)) from exc
        embedding_model = None
        embedding_dimension = None
        feature_status = "descriptor_ready"
        if self.allow_real_api:
            result = self.embedding.embed_text(descriptor, provider="dashscope_openai_compatible")
            embedding_model = result.model
            embedding_dimension = result.dimension
            feature_status = "active"
        item = existing or MediaSimilarityFeature(media_id=media_id)
        item.perceptual_hash = phash
        item.difference_hash = dhash
        item.ocr_normalized_text = self._normalize_ocr(media.ocr_text or "")
        item.visual_descriptor = descriptor
        item.device_model = analysis.device_models[0] if analysis.device_models else None
        item.fault_codes = analysis.fault_codes
        item.component_tags = analysis.component_terms
        item.embedding_model = embedding_model
        item.embedding_dimension = embedding_dimension
        item.content_hash = content_hash
        item.feature_status = feature_status
        item.metadata_json = {
            "capability_label": self.CAPABILITY_LABEL,
            "raw_image_embedding": False,
            "hash_method": hash_method,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def _knowledge_matches(self, descriptor: str, *, document_type: str, top_k: int) -> list[MultimodalMatch]:
        hits, _ = VectorIndexService(self.db, allow_real_api=self.allow_real_api).search(
            descriptor,
            top_k=top_k,
            filters={"device_type": "pv_inverter", "document_type": document_type},
        )
        object_type = "manual" if document_type == "manual" else "fault_case"
        return [
            MultimodalMatch(
                object_type=object_type,
                object_id=hit.chunk.id,
                title=hit.document.title,
                page_number=hit.chunk.page_number,
                section_title=hit.chunk.section_title,
                score_breakdown=MultimodalScoreBreakdown(
                    descriptor_vector_score=hit.score,
                    device_model_exact=1.0 if hit.metadata.get("device_model") else 0.0,
                    fault_code_exact=1.0 if hit.metadata.get("fault_codes") else 0.0,
                    final_score=hit.score,
                ),
            )
            for hit in hits
        ]

    def _similar_media(self, query: MediaSimilarityFeature, *, top_k: int) -> tuple[list[MultimodalMatch], dict]:
        if not self.allow_real_api:
            raise VectorStoreAdapterError("real similar-media vector search is disabled")
        embedding = self.embedding.embed_query(query.visual_descriptor, provider="dashscope_openai_compatible")
        adapter = DashVectorAdapter(
            endpoint=self.settings.DASHVECTOR_ENDPOINT,
            api_key=self.settings.DASHVECTOR_API_KEY,
            collection_name=self.settings.DASHVECTOR_PHYSICAL_MEDIA_COLLECTION,
            namespace=self.settings.DASHVECTOR_NAMESPACE,
            dimension=1024,
            metric="cosine",
            dtype="float",
            timeout_seconds=self.settings.DASHVECTOR_TIMEOUT_SECONDS,
            upsert_batch_size=self.settings.DASHVECTOR_UPSERT_BATCH_SIZE,
            allow_real_api=True,
        )
        adapter.ensure_collection(dimension=1024)
        vector_id = f"md_{hashlib.sha256(f'{query.media_id}|{query.content_hash}'.encode()).hexdigest()[:48]}"
        adapter.upsert_vectors([VectorRecord(
            vector_id=vector_id,
            vector=embedding.vectors[0],
            metadata={
                "media_id": str(query.media_id), "content_hash": query.content_hash,
                "embedding_model": embedding.model, "embedding_dimension": embedding.dimension,
                "embedding_version": self.settings.EMBEDDING_INDEX_VERSION, "object_type": "media_descriptor",
                "device_model": query.device_model or "", "fault_codes": ",".join(query.fault_codes or []),
                "status": "active",
            },
        )])
        query.vector_index_id = vector_id
        query.embedding_model = embedding.model
        query.embedding_dimension = embedding.dimension
        query.feature_status = "active"
        self.db.add(query)
        self.db.commit()
        raw_hits = []
        for _ in range(10):
            raw_hits = adapter.query_vectors(vector=embedding.vectors[0], top_k=top_k + 1)
            if len(raw_hits) > 1:
                break
            time.sleep(1)
        media_ids: list[UUID] = []
        hit_map = {}
        for hit in raw_hits:
            try:
                candidate_id = UUID(str(hit.metadata.get("media_id")))
            except (TypeError, ValueError):
                continue
            if candidate_id != query.media_id:
                media_ids.append(candidate_id)
                hit_map[candidate_id] = hit
        if not media_ids:
            return [], {"vector_available": True, "external_api_called": True, "candidate_count": 0}
        statement = select(MediaSimilarityFeature, UploadedMedia).join(UploadedMedia, UploadedMedia.id == MediaSimilarityFeature.media_id).where(
            MediaSimilarityFeature.media_id.in_(media_ids), MediaSimilarityFeature.feature_status == "active", UploadedMedia.status == "active"
        )
        matches: list[MultimodalMatch] = []
        for candidate, media in self.db.execute(statement).all():
            hit = hit_map[candidate.media_id]
            scores = self.similarity_breakdown(query, candidate, descriptor_vector_score=hit.score)
            matches.append(MultimodalMatch(
                object_type="media", object_id=candidate.media_id,
                title=media.original_file_name or media.file_name,
                score_breakdown=MultimodalScoreBreakdown(**scores),
            ))
        matches.sort(key=lambda item: item.score_breakdown.final_score, reverse=True)
        return matches[:top_k], {"vector_available": True, "external_api_called": True, "candidate_count": len(matches)}

    @classmethod
    def similarity_breakdown(cls, left: MediaSimilarityFeature, right: MediaSimilarityFeature, *, descriptor_vector_score: float) -> dict:
        ocr = cls._token_jaccard(left.ocr_normalized_text, right.ocr_normalized_text)
        phash = cls._hash_similarity(left.perceptual_hash, right.perceptual_hash)
        dhash = cls._hash_similarity(left.difference_hash, right.difference_hash)
        model = float(bool(left.device_model and left.device_model == right.device_model))
        faults = float(bool(set(left.fault_codes or []) & set(right.fault_codes or [])))
        components = cls._set_jaccard(left.component_tags or [], right.component_tags or [])
        final = 0.45 * descriptor_vector_score + 0.15 * ocr + 0.15 * phash + 0.10 * dhash + 0.08 * model + 0.05 * faults + 0.02 * components
        return {
            "descriptor_vector_score": round(descriptor_vector_score, 6), "ocr_token_score": round(ocr, 6),
            "perceptual_hash_score": round(phash, 6), "difference_hash_score": round(dhash, 6),
            "device_model_exact": model, "fault_code_exact": faults, "component_overlap": round(components, 6),
            "final_score": round(final, 6),
        }

    def _descriptor(self, media: UploadedMedia):
        metadata = media.metadata_json or {}
        visual_summary = str(metadata.get("visual_summary") or media.description or "未提供人工视觉摘要")
        source = " ".join([media.description or "", media.ocr_text or "", visual_summary, str(metadata.get("alarm_code") or "")])
        analysis = self.query_understanding.understand(source or "光伏逆变器现场图片")
        descriptor = "\n".join([
            f"设备型号：{', '.join(analysis.device_models) or '未识别'}",
            f"故障码：{', '.join(analysis.fault_codes) or '未识别'}",
            f"部件：{', '.join(analysis.component_terms) or '未识别'}",
            f"可见文字：{self._normalize_ocr(media.ocr_text or '')[:800] or '无'}",
            f"故障现象：{', '.join(analysis.symptom_terms) or media.description or '未识别'}",
            f"安全风险：{', '.join(analysis.safety_terms) or '需按电气检修规范人工确认'}",
            f"其他视觉特征：{visual_summary[:500]}",
        ])
        return descriptor, analysis

    @staticmethod
    def _image_hashes(path, metadata: dict | None = None) -> tuple[str, str, str]:
        metadata = metadata or {}
        phash = str(metadata.get("perceptual_hash") or "").lower()
        dhash = str(metadata.get("difference_hash") or "").lower()
        if re.fullmatch(r"[0-9a-f]{16}", phash) and re.fullmatch(r"[0-9a-f]{16}", dhash):
            return phash, dhash, "trusted_precomputed_phash_dhash"
        try:
            from PIL import Image
        except ImportError as exc:
            raise MultimodalRetrievalServiceError("Pillow is unavailable; perceptual hashes cannot be computed") from exc
        with Image.open(path) as image:
            gray = image.convert("L")
            small = gray.resize((32, 32))
            pixels = list(small.getdata())
            coeffs = []
            for u in range(8):
                for v in range(8):
                    value = 0.0
                    for x in range(32):
                        for y in range(32):
                            value += pixels[y * 32 + x] * math.cos((2 * x + 1) * u * math.pi / 64) * math.cos((2 * y + 1) * v * math.pi / 64)
                    coeffs.append(value)
            median = sorted(coeffs[1:])[len(coeffs[1:]) // 2]
            phash = f"{sum((1 << index) for index, value in enumerate(coeffs) if value > median):016x}"
            diff = list(gray.resize((9, 8)).getdata())
            bits = [diff[row * 9 + col] > diff[row * 9 + col + 1] for row in range(8) for col in range(8)]
            dhash = f"{sum((1 << index) for index, value in enumerate(bits) if value):016x}"
        return phash, dhash, "pillow_dct_phash_and_dhash"

    @staticmethod
    def _normalize_ocr(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    @staticmethod
    def _token_jaccard(left: str, right: str) -> float:
        return MultimodalRetrievalService._set_jaccard(re.findall(r"[\w\u4e00-\u9fff-]+", left.lower()), re.findall(r"[\w\u4e00-\u9fff-]+", right.lower()))

    @staticmethod
    def _set_jaccard(left, right) -> float:
        a, b = set(left), set(right)
        return len(a & b) / len(a | b) if a or b else 0.0

    @staticmethod
    def _hash_similarity(left: str, right: str) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        distance = (int(left, 16) ^ int(right, 16)).bit_count()
        return 1.0 - distance / (len(left) * 4)
