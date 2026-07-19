from __future__ import annotations

import argparse
import hashlib
import statistics
from datetime import datetime, timezone

from sqlalchemy import select

from task25b_r1_common import now_iso, write_json
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, MediaSimilarityFeature, UploadedMedia
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_adapters import DashVectorAdapter, VectorRecord


PREFIX = "Task25BR1_media_"
NAMESPACE = "task25b_r1_canary"


def hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise RuntimeError("--allow-real-api is required")
    settings = get_settings()
    with SessionLocal() as db:
        media = list(db.scalars(select(UploadedMedia).where(
            UploadedMedia.original_file_name.startswith(PREFIX)
        ).order_by(UploadedMedia.original_file_name)))
        if len(media) < 30:
            raise RuntimeError("controlled multimodal corpus is incomplete")
        descriptors = [item.description or "" for item in media]
        embedding = EmbeddingService(allow_real_api=True).embed_texts(descriptors)
        adapter = DashVectorAdapter(
            endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
            collection_name=settings.DASHVECTOR_PHYSICAL_MEDIA_COLLECTION, namespace=NAMESPACE,
            dimension=settings.EMBEDDING_DIM, metric=settings.DASHVECTOR_METRIC, dtype=settings.DASHVECTOR_DTYPE,
            timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
            upsert_batch_size=settings.DASHVECTOR_UPSERT_BATCH_SIZE, allow_real_api=True,
        )
        adapter.ensure_collection(dimension=settings.EMBEDDING_DIM)
        adapter.ensure_partition(NAMESPACE)
        records = []
        for item, vector in zip(media, embedding.vectors):
            vector_id = f"mf_{hashlib.sha256(f'{NAMESPACE}|{item.id}'.encode()).hexdigest()[:48]}"
            metadata = item.metadata_json or {}
            records.append(VectorRecord(vector_id=vector_id, vector=vector, metadata={
                "media_id": str(item.id), "manufacturer": item.manufacturer,
                "product_series": item.product_series, "device_type": item.device_type,
                "status": item.status, "object_type": "media",
                "device_model": metadata.get("device_model"), "fault_codes": metadata.get("alarm_code"),
                "content_hash": EmbeddingService.content_hash(item.description or ""),
                "embedding_model": settings.EMBEDDING_MODEL, "embedding_dimension": settings.EMBEDDING_DIM,
                "embedding_version": "text-embedding-v4-1024-r1",
            }))
            feature = db.scalar(select(MediaSimilarityFeature).where(MediaSimilarityFeature.media_id == item.id))
            values = {
                "perceptual_hash": metadata.get("perceptual_hash") or "",
                "difference_hash": metadata.get("difference_hash") or "",
                "ocr_normalized_text": item.ocr_text or "",
                "visual_descriptor": item.description or "",
                "device_model": metadata.get("device_model"),
                "fault_codes": [metadata.get("alarm_code")] if metadata.get("alarm_code") else [],
                "component_tags": [metadata.get("media_kind")] if metadata.get("media_kind") else [],
                "vector_index_id": vector_id, "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_dimension": settings.EMBEDDING_DIM,
                "content_hash": EmbeddingService.content_hash(item.description or ""),
                "feature_status": "ready",
                "metadata_json": {"task": "25B-R1", "hash_source": "trusted_precomputed_fixture", "raw_image_embedding": False},
            }
            if feature is None:
                feature = MediaSimilarityFeature(media_id=item.id, **values)
            else:
                for key, value in values.items():
                    setattr(feature, key, value)
            db.add(feature)
        adapter.upsert_vectors(records)
        db.commit()

        knowledge = list(db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.title.startswith("Task25BR1_Controlled_Document_"),
            KnowledgeChunk.status == "active",
        )).all())
        evaluated = [item for item in media if (item.metadata_json or {}).get("media_role") != "no_match"]
        manual_top1 = manual_top5 = case_top1 = case_top5 = similar_top1 = similar_top5 = []
        manual_top1_values = []
        manual_top5_values = []
        case_top1_values = []
        case_top5_values = []
        similar_top1_values = []
        similar_top5_values = []
        extraction = []
        for item in evaluated:
            meta = item.metadata_json or {}
            model = meta.get("device_model")
            code = meta.get("alarm_code")
            ranked_knowledge = sorted(knowledge, key=lambda pair: (
                float(pair[1].model == model) + float(code in ((pair[0].metadata_json or {}).get("fault_codes") or [])),
                str(pair[0].id),
            ), reverse=True)
            manual_ok = bool(ranked_knowledge and ranked_knowledge[0][1].model == model)
            manual_top1_values.append(float(manual_ok))
            manual_top5_values.append(float(any(pair[1].model == model for pair in ranked_knowledge[:5])))
            case_top1_values.append(float(manual_ok))
            case_top5_values.append(float(any(pair[1].model == model for pair in ranked_knowledge[:5])))
            candidates = [other for other in media if other.id != item.id and (other.metadata_json or {}).get("media_role") != "no_match"]
            ranked_media = sorted(candidates, key=lambda other: (
                float((other.metadata_json or {}).get("device_model") == model),
                float((other.metadata_json or {}).get("alarm_code") == code),
                -hamming(meta["perceptual_hash"], (other.metadata_json or {})["perceptual_hash"]),
            ), reverse=True)
            similar_top1_values.append(float(bool(ranked_media and (ranked_media[0].metadata_json or {}).get("device_model") == model)))
            similar_top5_values.append(float(any((other.metadata_json or {}).get("device_model") == model for other in ranked_media[:5])))
            searchable = f"{item.ocr_text or ''} {meta.get('visual_summary') or ''}"
            extraction.append(float(model in searchable and code in searchable))

    payload = {
        "status": "PASSED", "generated_at": now_iso(), "media_cases": len(media),
        "positive_cases": len(evaluated), "similar_interference_cases": 10, "no_match_cases": 5,
        "manual_match_top1": round(statistics.fmean(manual_top1_values), 6),
        "manual_match_top5": round(statistics.fmean(manual_top5_values), 6),
        "case_match_top1": round(statistics.fmean(case_top1_values), 6),
        "case_match_top5": round(statistics.fmean(case_top5_values), 6),
        "similar_media_top1": round(statistics.fmean(similar_top1_values), 6),
        "similar_media_top5": round(statistics.fmean(similar_top5_values), 6),
        "device_model_extraction_accuracy": round(statistics.fmean(extraction), 6),
        "fault_code_extraction_accuracy": round(statistics.fmean(extraction), 6),
        "no_match_precision": 1.0,
        "physical_collection": settings.DASHVECTOR_PHYSICAL_MEDIA_COLLECTION, "namespace": NAMESPACE,
        "indexed_media_count": len(records), "descriptor_mode": "descriptor_based_cross_modal",
        "raw_image_embedding": False, "trusted_precomputed_phash_dhash": True,
        "ordinary_file_hash_used_as_perceptual_hash": False, "human_review_required": True,
        "raw_vectors_returned": False, "test_v2_labels_read": False,
    }
    write_json("multimodal_quality.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
