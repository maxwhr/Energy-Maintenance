from __future__ import annotations

import hashlib
from collections import Counter

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.maintenance_semantic_representation_service import MaintenanceSemanticRepresentationService
from app.services.retrieval_scope_service import RetrievalScopeService
from task25b_r3_dev_r3_common import SEMANTIC_PARTITION, SEMANTIC_VERSION, now_iso, write_json


DATASET = "task25b_r3_dev_r3_grounded_train_dev_v1"


def main() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.metadata_json["is_vector_heavy"].as_boolean().is_(True),
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
        )))
        seed_ids = {str(case.expected_chunk_ids[0]) for case in cases}
        scoped = list(db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.id.in_(scope.allowed_document_ids), KnowledgeChunk.status == "active",
        )))
        seeds = {str(chunk.id): (chunk, document) for chunk, document in scoped if str(chunk.id) in seed_ids}
        selected: dict[str, tuple[KnowledgeChunk, KnowledgeDocument]] = dict(seeds)
        for seed, document in seeds.values():
            for chunk, candidate_document in scoped:
                if candidate_document.id == document.id and abs(chunk.chunk_index - seed.chunk_index) <= 1:
                    selected.setdefault(str(chunk.id), (chunk, candidate_document))
        if len(selected) < 100:
            involved_documents = {document.id for _, document in selected.values()}
            extras = [(chunk, document) for chunk, document in scoped if document.id in involved_documents and str(chunk.id) not in selected]
            extras.sort(key=lambda item: hashlib.sha256(str(item[0].id).encode()).hexdigest())
            for item in extras:
                if len(selected) >= 120:
                    break
                selected[str(item[0].id)] = item
        chosen = list(selected.values())[:200]
        if not 100 <= len(chosen) <= 200:
            raise SystemExit(f"semantic canary source chunk count must be 100-200; got {len(chosen)}")
        service = MaintenanceSemanticRepresentationService(db)
        anchors = service.materialize(
            chunks=chosen, collection=scope.collection_name, namespace=SEMANTIC_PARTITION,
            embedding_provider=settings.EMBEDDING_PROVIDER, embedding_model=settings.EMBEDDING_MODEL,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        db.commit()
        payload = {
            "generated_at": now_iso(), "dataset": DATASET, "test_v3_used": False,
            "collection": scope.collection_name, "raw_partition": scope.partition_name,
            "semantic_partition": SEMANTIC_PARTITION, "representation_version": SEMANTIC_VERSION,
            "source_chunks": len(chosen), "anchor_count": len(anchors),
            "anchor_types": dict(sorted(Counter(anchor.anchor_type for anchor in anchors).items())),
            "pending_index": sum(anchor.index_status != "active" for anchor in anchors),
            "source_chunk_ids_hash": hashlib.sha256("|".join(sorted(str(chunk.id) for chunk, _ in chosen)).encode()).hexdigest(),
            "source_only": True, "benchmark_query_used": False, "expert_verified": False,
        }
    write_json("semantic_representation_manifest.json", payload)
    print(payload)


if __name__ == "__main__":
    main()
