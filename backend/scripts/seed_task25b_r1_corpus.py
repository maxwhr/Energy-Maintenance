from __future__ import annotations

import argparse
import hashlib
import random
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from task25b_r1_common import BACKEND, now_iso, sha256_text, write_json
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument, RetrievalEvaluationCase, UploadedMedia, User
from app.repositories.vector_index_repository import VectorIndexRepository
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_adapters import DashVectorAdapter, VectorRecord, VectorStoreAdapterError


SEED = 25001
PREFIX = "Task25BR1_"
DATASET_VERSION = "task25b-r1-v2"
MODELS = [
    "SUN2000-50KTL-M3", "SUN2000-60KTL-M0", "SUN2000-100KTL-M2", "SUN2000-115KTL-M2",
    "SUN2000-196KTL-H0", "SUN2000-215KTL-H3", "SG50CX", "SG60CX", "SG110CX",
    "SG125CX-P2", "SG225HX", "SG320HX",
]
FAULT_CODES = [
    "2001", "2002", "2003", "2011", "2021", "2031", "2032", "2041", "2051", "2064",
    "2065", "2071", "2081", "2090", "2101", "2110", "2120", "2130", "2140", "2150",
]
CATEGORIES = [
    "device_model_query", "fault_code_query", "fault_symptom_query", "manual_section_location",
    "safety_operation_query", "image_ocr_query", "image_visual_descriptor_query", "similar_history_case",
    "no_answer", "interference_filter",
]
SPLIT_COUNTS = {"train": 72, "dev": 54, "test_v2": 54}
SPLIT_DOCS = {"train": range(0, 8), "dev": range(8, 16), "test_v2": range(16, 24)}


def _manufacturer(model: str) -> str:
    return "huawei" if model.startswith("SUN2000") else "sungrow"


def _series(model: str) -> str:
    return "SUN2000" if model.startswith("SUN2000") else "SG"


def _content(doc_index: int, chunk_index: int, model: str, fault_code: str, hard_negative: bool) -> str:
    token = f"T25BR1-E-{doc_index + 1:02d}-{chunk_index + 1:02d}"
    section = (
        "相似标题干扰说明" if hard_negative else
        ["型号适用范围", "故障码定义", "故障现象排查", "手册章节定位", "安全隔离操作", "历史维修案例"][chunk_index % 6]
    )
    qualifier = "本段是受控硬负例，仅用于检验相似标题与错误上下文过滤。" if hard_negative else "本段是受控正确证据。"
    return (
        f"{token} {model} 告警代码 {fault_code}。{section}：光伏逆变器维护时应核对设备完整型号、"
        f"告警上下文和章节来源。{qualifier} 执行断电、验电、放电、锁定挂牌并佩戴 PPE；"
        "禁止仅凭单一现象给出确定性故障结论。"
    )


def _query(category: str, *, token: str, model: str, fault_code: str, index: int) -> str:
    if category == "device_model_query":
        return f"{model} {token} 型号适用范围是什么"
    if category == "fault_code_query":
        return f"{model} 告警 {fault_code} {token} 表示什么"
    if category == "fault_symptom_query":
        return f"{token} 逆变器雨后间歇停机并出现绝缘异常如何排查"
    if category == "manual_section_location":
        return f"{token} 在手册哪个章节可以找到直流侧检查步骤"
    if category == "safety_operation_query":
        return f"{token} 检修前断电验电放电和锁定挂牌要求"
    if category == "image_ocr_query":
        return f"OCR 识别到 {model} ALARM {fault_code} {token} 应匹配哪段手册"
    if category == "image_visual_descriptor_query":
        return f"图片描述为 {model} 红色告警灯和直流绝缘异常 {token}"
    if category == "similar_history_case":
        return f"查找与 {token} {model} {fault_code} 相似的历史维修案例"
    if category == "interference_filter":
        return f"{token} {model} {fault_code}，排除过期和未审批资料"
    return f"不存在的型号 Task25BR1-UNKNOWN-{index:03d} 和未收录告警 X{index:04d}"


def _create_document(db, user: User, doc_index: int) -> tuple[KnowledgeDocument, list[KnowledgeChunk]]:
    title = f"{PREFIX}Controlled_Document_{doc_index + 1:02d}"
    document = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == title))
    model = MODELS[doc_index % len(MODELS)]
    if document is None:
        document = KnowledgeDocument(
            title=title, manufacturer=_manufacturer(model), product_series=_series(model), model=model,
            device_type="pv_inverter", document_type=("manual", "alarm_code", "sop", "fault_case")[doc_index % 4],
            source="Task 25B-R1 engineering controlled corpus", source_type="task25b_r1_engineering_controlled",
            file_name=f"{title}.txt", file_ext="txt", file_size=4096, page_count=8,
            parse_status="parsed", parser_name="task25b_r1_fixture_v1", chunk_count=8,
            summary="Engineering-controlled retrieval benchmark; not enterprise annotation.",
            parsed_at=datetime.now(timezone.utc), review_status="approved", submitted_by=user.id,
            reviewed_by=user.id, reviewed_at=datetime.now(timezone.utc), status="active",
            metadata_json={
                "task": "25B-R1", "dataset_version": DATASET_VERSION, "engineering_controlled": True,
                "generator_seed": SEED, "document_partition": next(name for name, values in SPLIT_DOCS.items() if doc_index in values),
            },
        )
        db.add(document)
        db.flush()
    chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.chunk_index)))
    if not chunks:
        for chunk_index in range(8):
            fault_code = FAULT_CODES[(doc_index * 3 + chunk_index) % len(FAULT_CODES)]
            hard_negative = chunk_index < 2
            content = _content(doc_index, chunk_index, model, fault_code, hard_negative)
            chunk = KnowledgeChunk(
                document_id=document.id, manufacturer=document.manufacturer, product_series=document.product_series,
                device_type="pv_inverter", document_type=document.document_type, chunk_index=chunk_index,
                content=content, content_hash=EmbeddingService.content_hash(content),
                section_title=("相似标题干扰" if hard_negative else f"{model} {fault_code} 维护证据"),
                char_count=len(content), page_number=chunk_index + 1, embedding_status="pending", status="active",
                metadata_json={
                    "task": "25B-R1", "dataset_version": DATASET_VERSION, "engineering_controlled": True,
                    "evidence_token": f"T25BR1-E-{doc_index + 1:02d}-{chunk_index + 1:02d}",
                    "device_models": [model], "fault_codes": [fault_code],
                    "hard_negative": hard_negative, "section_path": [document.document_type, str(chunk_index + 1)],
                    "generator_seed": SEED,
                },
            )
            db.add(chunk)
            chunks.append(chunk)
        db.flush()
    return document, chunks


def _create_interference_documents(db, user: User) -> None:
    definitions = [
        ("Pending", "pending", "draft", "active"),
        ("Archived", "parsed", "approved", "archived"),
        ("Rejected", "parsed", "rejected", "active"),
        ("Deleted", "parsed", "approved", "deleted"),
    ]
    for index, (label, parse_status, review_status, status) in enumerate(definitions):
        title = f"{PREFIX}Interference_{label}"
        if db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == title)):
            continue
        document = KnowledgeDocument(
            title=title, manufacturer="huawei", product_series="SUN2000", model="SUN2000-100KTL-M2",
            device_type="pv_inverter", document_type="manual", source="Task 25B-R1 interference fixture",
            source_type="task25b_r1_interference", file_name=f"{title}.txt", file_ext="txt", file_size=256,
            page_count=1, parse_status=parse_status, parser_name="task25b_r1_fixture_v1",
            chunk_count=1 if parse_status == "parsed" else 0, summary="Controlled lifecycle interference fixture.",
            parsed_at=datetime.now(timezone.utc) if parse_status == "parsed" else None,
            review_status=review_status, submitted_by=user.id,
            reviewed_by=user.id if review_status == "approved" else None,
            reviewed_at=datetime.now(timezone.utc) if review_status == "approved" else None,
            status=status, metadata_json={"task": "25B-R1", "engineering_controlled": True, "must_not_index": True},
        )
        db.add(document)
        db.flush()
        if parse_status == "parsed":
            content = f"Task25BR1 interference {label} SUN2000-100KTL-M2 2064 must not be retrieved."
            db.add(KnowledgeChunk(
                document_id=document.id, manufacturer="huawei", product_series="SUN2000", device_type="pv_inverter",
                document_type="manual", chunk_index=0, content=content,
                content_hash=EmbeddingService.content_hash(content), section_title="Interference", char_count=len(content),
                page_number=1, embedding_status="pending", status="active",
                metadata_json={"task": "25B-R1", "must_not_index": True, "generator_seed": SEED},
            ))


def _create_cases(db, user: User, docs: list[tuple[KnowledgeDocument, list[KnowledgeChunk]]]) -> int:
    created = 0
    global_index = 0
    for split, count in SPLIT_COUNTS.items():
        split_docs = list(SPLIT_DOCS[split])
        for local_index in range(count):
            category = CATEGORIES[local_index % len(CATEGORIES)]
            name = f"{PREFIX}{split}_{local_index + 1:03d}"
            if db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name)):
                global_index += 1
                continue
            doc_index = split_docs[(local_index // len(CATEGORIES)) % len(split_docs)]
            document, chunks = docs[doc_index]
            target_candidates = [item for item in chunks if not (item.metadata_json or {}).get("hard_negative")]
            target = target_candidates[local_index % len(target_candidates)]
            metadata = target.metadata_json or {}
            model = (metadata.get("device_models") or [document.model])[0]
            fault_code = (metadata.get("fault_codes") or ["2064"])[0]
            token = metadata["evidence_token"]
            no_answer = category == "no_answer"
            query = _query(category, token=token, model=model, fault_code=fault_code, index=global_index)
            db.add(RetrievalEvaluationCase(
                name=name, category=category, query_text=query,
                expected_document_ids=[] if no_answer else [str(document.id)],
                expected_chunk_ids=[] if no_answer else [str(target.id)], expected_media_ids=[],
                required_filters={
                    "manufacturer": document.manufacturer, "product_series": document.product_series,
                    "device_type": "pv_inverter",
                } if not no_answer else {"device_type": "pv_inverter"},
                excluded_document_ids=[], difficulty="hard" if category in {"interference_filter", "no_answer"} else "medium",
                # Migration 0009 constrains the physical value to train/dev/test.
                # R1 keeps the schema unchanged and records the independent logical split in metadata.
                dataset_split="test" if split == "test_v2" else split, review_status="engineering_verified",
                source_type="task25b_r1_engineering_controlled",
                metadata_json={
                    "dataset_version": DATASET_VERSION, "engineering_controlled": True, "generator_seed": SEED,
                    "document_partition": split, "logical_split": split, "labels_frozen": False,
                },
                created_by=user.id, reviewed_by=user.id,
            ))
            created += 1
            global_index += 1
    return created


def _create_media(db, user: User) -> int:
    existing_fixture = db.scalar(select(UploadedMedia).where(UploadedMedia.original_file_name == "Task25B_controlled_probe.png"))
    relative_path = existing_fixture.file_path if existing_fixture else "storage/uploads/media/task25b/Task25B_controlled_probe.png"
    created = 0
    for index in range(30):
        name = f"{PREFIX}media_{index + 1:02d}.png"
        if db.scalar(select(UploadedMedia).where(UploadedMedia.original_file_name == name)):
            continue
        model = MODELS[index % len(MODELS)]
        code = FAULT_CODES[index % len(FAULT_CODES)]
        kind = ("nameplate", "alarm_screen", "device_exterior", "fault_component")[index % 4]
        role = "no_match" if index >= 25 else "similar_interference" if index >= 15 else "positive"
        db.add(UploadedMedia(
            file_name=name, original_file_name=name, file_path=relative_path, file_ext="png", mime_type="image/png",
            file_size=existing_fixture.file_size if existing_fixture else 68, media_type="fault_image",
            description=f"Task25BR1 {kind} descriptor {model} alarm {code} role {role}",
            ocr_text=f"{model} ALARM {code}" if kind in {"nameplate", "alarm_screen"} else "",
            manufacturer=_manufacturer(model), product_series=_series(model), device_type="pv_inverter",
            uploaded_by=user.id, status="active",
            metadata_json={
                "task": "25B-R1", "engineering_controlled": True, "media_role": role, "media_kind": kind,
                "device_model": model, "alarm_code": code, "visual_summary": f"{kind} {model} {code}",
                "perceptual_hash": f"{index:016x}", "difference_hash": f"{(index * 3):016x}",
                "hash_source": "trusted_precomputed_fixture", "raw_image_embedding": False,
            },
        ))
        created += 1
    return created


def _index_canary(db, settings) -> dict:
    collection = settings.DASHVECTOR_R1_CANARY_COLLECTION
    physical_collection = collection
    namespace = settings.DASHVECTOR_NAMESPACE
    chunks = list(db.execute(
        select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.title.startswith(f"{PREFIX}Controlled_Document_"),
            KnowledgeDocument.review_status == "approved", KnowledgeDocument.status == "active",
            KnowledgeDocument.parse_status == "parsed", KnowledgeChunk.status == "active",
        ).order_by(KnowledgeDocument.title, KnowledgeChunk.chunk_index)
    ).all())
    existing = int(db.scalar(select(func.count()).select_from(KnowledgeChunkVectorIndex).where(
        KnowledgeChunkVectorIndex.collection_name == collection,
        KnowledgeChunkVectorIndex.namespace == "task25b_r1_canary",
        KnowledgeChunkVectorIndex.index_status == "active",
    )) or 0)
    if existing == len(chunks) and existing >= 160:
        return {"collection": collection, "vectors": existing, "indexed": 0, "skipped": existing, "external_api_called": False}
    adapter = DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
        collection_name=physical_collection, namespace=namespace,
        dimension=settings.EMBEDDING_DIM, metric=settings.DASHVECTOR_METRIC,
        dtype=settings.DASHVECTOR_DTYPE, timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
        upsert_batch_size=settings.DASHVECTOR_UPSERT_BATCH_SIZE, allow_real_api=True,
    )
    physical_mapping_reason = None
    try:
        adapter.ensure_collection(dimension=settings.EMBEDDING_DIM)
    except VectorStoreAdapterError as exc:
        if "Collection num exceeds limit" not in str(exc):
            raise
        physical_collection = settings.DASHVECTOR_PHYSICAL_COLLECTION
        namespace = "task25b_r1_canary"
        physical_mapping_reason = "provider_collection_quota_2_partition_isolation_used"
        adapter = DashVectorAdapter(
            endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
            collection_name=physical_collection, namespace=namespace,
            dimension=settings.EMBEDDING_DIM, metric=settings.DASHVECTOR_METRIC,
            dtype=settings.DASHVECTOR_DTYPE, timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
            upsert_batch_size=settings.DASHVECTOR_UPSERT_BATCH_SIZE, allow_real_api=True,
        )
        adapter.ensure_collection(dimension=settings.EMBEDDING_DIM)
        adapter.ensure_partition(namespace)
    embedding = EmbeddingService(allow_real_api=True).embed_texts([chunk.content for chunk, _ in chunks])
    records = []
    contexts = []
    for (chunk, document), vector in zip(chunks, embedding.vectors):
        scope = f"{collection}|{namespace}|{chunk.id}"
        vector_id = f"kc_{hashlib.sha256(scope.encode('utf-8')).hexdigest()[:48]}"
        metadata = {
            "chunk_id": str(chunk.id), "document_id": str(document.id), "document_title": document.title,
            "chunk_index": chunk.chunk_index, "manufacturer": document.manufacturer,
            "product_series": document.product_series, "device_type": document.device_type,
            "document_type": document.document_type, "review_status": document.review_status,
            "parse_status": document.parse_status, "status": document.status,
            "content_hash": chunk.content_hash, "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimension": settings.EMBEDDING_DIM, "embedding_version": "text-embedding-v4-1024-r1",
            "device_model": document.model,
            "fault_codes": ",".join((chunk.metadata_json or {}).get("fault_codes", [])),
            "section_path": str((chunk.metadata_json or {}).get("section_path") or []),
            "page_number": chunk.page_number, "object_type": "knowledge_chunk",
        }
        records.append(VectorRecord(vector_id=vector_id, vector=vector, metadata=metadata))
        contexts.append((chunk, document, vector_id, metadata))
    adapter.upsert_vectors(records)
    repository = VectorIndexRepository(db)
    for chunk, document, vector_id, metadata in contexts:
        repository.upsert_index(
            chunk=chunk, document=document, vector_backend="dashvector", collection_name=collection,
            namespace=namespace, vector_id=vector_id,
            embedding_model=settings.EMBEDDING_MODEL, embedding_provider=settings.EMBEDDING_PROVIDER,
            embedding_dim=settings.EMBEDDING_DIM, content_hash=chunk.content_hash or EmbeddingService.content_hash(chunk.content),
            metadata_json={**metadata, "raw_vector_stored_in_postgresql": False, "task": "25B-R1"},
        )
    db.commit()
    return {
        "logical_collection": collection, "physical_collection": physical_collection, "namespace": namespace,
        "physical_mapping_reason": physical_mapping_reason, "vectors": len(records), "indexed": len(records),
        "skipped": 0, "external_api_called": True, "v1_default_partition_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise RuntimeError("--allow-real-api and TASK25B_ALLOW_REAL_API=true are required for the controlled R1 workflow")
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise RuntimeError("TASK25B_ALLOW_FULL_REINDEX must remain false")
    random.seed(SEED)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        if user is None:
            raise RuntimeError("admin user is required")
        docs = [_create_document(db, user, index) for index in range(24)]
        _create_interference_documents(db, user)
        created_cases = _create_cases(db, user, docs)
        created_media = _create_media(db, user)
        db.commit()
        canary = _index_canary(db, settings)
        controlled_documents = int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.title.startswith(f"{PREFIX}Controlled_Document_")
        )) or 0)
        active_chunks = int(db.scalar(select(func.count()).select_from(KnowledgeChunk).join(KnowledgeDocument).where(
            KnowledgeDocument.title.startswith(f"{PREFIX}Controlled_Document_"),
            KnowledgeDocument.review_status == "approved", KnowledgeDocument.status == "active",
            KnowledgeDocument.parse_status == "parsed", KnowledgeChunk.status == "active",
        )) or 0)
        hard_negatives = int(db.scalar(select(func.count()).select_from(KnowledgeChunk).join(KnowledgeDocument).where(
            KnowledgeDocument.title.startswith(f"{PREFIX}Controlled_Document_"),
            KnowledgeChunk.metadata_json["hard_negative"].as_boolean() == True,  # noqa: E712
        )) or 0)
        case_counts = {}
        for split in SPLIT_COUNTS:
            filters = [
                RetrievalEvaluationCase.source_type == "task25b_r1_engineering_controlled",
                RetrievalEvaluationCase.dataset_split == ("test" if split == "test_v2" else split),
            ]
            if split == "test_v2":
                filters.append(RetrievalEvaluationCase.metadata_json["logical_split"].as_string() == "test_v2")
            case_counts[split] = int(db.scalar(
                select(func.count()).select_from(RetrievalEvaluationCase).where(*filters)
            ) or 0)
        media_count = int(db.scalar(select(func.count()).select_from(UploadedMedia).where(
            UploadedMedia.original_file_name.startswith(f"{PREFIX}media_")
        )) or 0)

    payload = {
        "status": "PASSED" if controlled_documents >= 24 and active_chunks >= 160 and hard_negatives >= 40 and case_counts == SPLIT_COUNTS and media_count >= 30 else "FAILED",
        "generated_at": now_iso(), "dataset_version": DATASET_VERSION, "generator_seed": SEED,
        "generator_rules_sha256": sha256_text(Path(__file__).read_text(encoding="utf-8")),
        "controlled_documents": controlled_documents, "active_chunks": active_chunks,
        "device_models": len(MODELS), "fault_codes": len(FAULT_CODES), "hard_negatives": hard_negatives,
        "case_counts": case_counts, "media_cases": media_count, "created_cases": created_cases,
        "created_media": created_media, "engineering_controlled": True, "expert_verified": False,
        "formal_knowledge_modified": False, "formal_full_reindex_performed": False,
        "canary_index_performed": bool(canary["vectors"]), "canary": canary,
        "task25b_allow_full_reindex": settings.TASK25B_ALLOW_FULL_REINDEX,
    }
    write_json("corpus_seed.json", payload)
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
