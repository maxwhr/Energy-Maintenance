from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from task25b_common import BACKEND, write_result
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase, UploadedMedia, User
from app.services.embedding_service import EmbeddingService


CATEGORIES = {
    "device_model_query": ("SUN2000-100KTL-M2 型号参数与适用范围", "manual"),
    "fault_code_query": ("告警码 2064 表示直流侧绝缘阻抗偏低，须断电、验电并按手册排查。", "alarm_code"),
    "fault_symptom_query": ("逆变器雨后间歇出现绝缘阻抗低并停止并网。", "fault_case"),
    "manual_section_location": ("第 5.3 节 绝缘阻抗排查：检查组串、接地与直流电缆。", "manual"),
    "safety_operation_query": ("高压危险：执行锁定挂牌、断电、验电、放电并佩戴 PPE。", "sop"),
    "image_ocr_query": ("现场屏幕 OCR 可见文字 SUN2000-100KTL 告警 2064。", "fault_case"),
    "image_visual_descriptor_query": ("视觉描述：逆变器面板红色告警灯，直流组串绝缘异常。", "fault_case"),
    "similar_history_case": ("历史案例：SUN2000 雨后 2064，修复破损直流电缆后恢复。", "fault_case"),
}

QUERIES = {
    "device_model_query": "SUN2000-100KTL-M2 型号参数与适用范围",
    "fault_code_query": "告警码 2064 直流侧绝缘阻抗偏低",
    "fault_symptom_query": "雨后间歇绝缘阻抗低并停止并网",
    "manual_section_location": "第 5.3 节 组串接地与直流电缆检查",
    "safety_operation_query": "锁定挂牌 断电 验电 放电 PPE",
    "image_ocr_query": "现场屏幕 OCR SUN2000-100KTL-M2 ALARM 2064",
    "image_visual_descriptor_query": "逆变器面板红色告警灯 直流组串绝缘异常",
    "similar_history_case": "修复破损直流电缆后恢复并网 历史案例",
}


def create_document(db, category, content, document_type, user, review_status="approved"):
    title = f"Task25B_{category} controlled knowledge"
    existing = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == title))
    if existing:
        chunk = db.scalar(select(KnowledgeChunk).where(KnowledgeChunk.document_id == existing.id).order_by(KnowledgeChunk.chunk_index))
        return existing, chunk
    document = KnowledgeDocument(
        title=title, manufacturer="huawei", product_series="SUN2000", model="SUN2000-100KTL-M2",
        device_type="pv_inverter", document_type=document_type, source="Task25B controlled benchmark",
        source_type="task25b_engineering_fixture", file_name=f"{title}.txt", file_ext="txt", file_size=len(content.encode()),
        page_count=1, parse_status="parsed", parser_name="structured_parser_v1", chunk_count=1,
        summary=f"Task25B engineering-controlled {category} evidence.", parsed_at=datetime.now(timezone.utc),
        review_status=review_status, submitted_by=user.id, reviewed_by=user.id if review_status == "approved" else None,
        reviewed_at=datetime.now(timezone.utc) if review_status == "approved" else None,
        status="active", metadata_json={"task": "25B", "category": category, "engineering_fixture": True},
    )
    db.add(document); db.flush()
    chunk = KnowledgeChunk(
        document_id=document.id, manufacturer="huawei", product_series="SUN2000", device_type="pv_inverter",
        document_type=document_type, chunk_index=0, content=content, content_hash=EmbeddingService.content_hash(content),
        section_title=f"Task25B {category}", char_count=len(content), page_number=1, embedding_status="pending",
        metadata_json={"parser_version": "structured_parser_v1", "chunker_version": "semantic_chunker_v1",
                       "section_path": [category], "device_models": ["SUN2000-100KTL-M2"], "fault_codes": ["2064"],
                       "source_locator": {"page_number": 1, "section_path": [category]}}, status="active",
    )
    db.add(chunk); db.flush()
    return document, chunk


def create_media(db, user):
    name = "Task25B_controlled_probe.png"
    existing = db.scalar(select(UploadedMedia).where(UploadedMedia.original_file_name == name))
    if existing:
        return existing
    # Valid 1x1 PNG fixture; no external image or base64 is returned by any API/report.
    data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z5ZkAAAAASUVORK5CYII=")
    relative = Path("storage/uploads/media/task25b") / name
    target = BACKEND / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    media = UploadedMedia(
        file_name=name, original_file_name=name, file_path=relative.as_posix(), file_ext="png", mime_type="image/png",
        file_size=len(data), media_type="fault_image", description="SUN2000 面板红色告警灯，雨后直流绝缘异常",
        ocr_text="SUN2000-100KTL-M2 ALARM 2064", manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", uploaded_by=user.id, status="active",
        metadata_json={"task": "25B", "ocr_status": "processed", "alarm_code": "2064",
                       "visual_summary": "逆变器面板红色告警灯，直流组串绝缘异常",
                       "perceptual_hash": "8000000000000000", "difference_hash": "0000000000000000"},
    )
    db.add(media); db.flush()
    return media


def main() -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        if not user:
            write_result("benchmark_seed.json", {"status": "BLOCKED", "reason": "admin user not found"})
            return 2
        evidence = {category: create_document(db, category, *values, user) for category, values in CATEGORIES.items()}
        interference = create_document(db, "interference_pending", "SUN2000-100KTL-M2 2064 干扰文档，不得召回。", "manual", user, "draft")
        media = create_media(db, user)
        media.metadata_json = {**(media.metadata_json or {}), "perceptual_hash": "8000000000000000", "difference_hash": "0000000000000000"}
        db.add(media)
        second_name = "Task25B_controlled_probe_similar.png"
        second_media = db.scalar(select(UploadedMedia).where(UploadedMedia.original_file_name == second_name))
        if not second_media:
            second_media = UploadedMedia(
                file_name=second_name, original_file_name=second_name, file_path=media.file_path,
                file_ext="png", mime_type="image/png", file_size=media.file_size, media_type="fault_image",
                description="SUN2000 面板红色告警灯，直流绝缘阻抗偏低", ocr_text="SUN2000-100KTL-M2 ALARM 2064",
                manufacturer="huawei", product_series="SUN2000", device_type="pv_inverter", uploaded_by=user.id,
                status="active", metadata_json={"task": "25B", "ocr_status": "processed", "alarm_code": "2064",
                "visual_summary": "逆变器面板红灯，直流组串绝缘异常，相似历史媒体",
                "perceptual_hash": "8000000000000000", "difference_hash": "0000000000000000"},
            )
            db.add(second_media)
            db.flush()
        else:
            second_media.metadata_json = {**(second_media.metadata_json or {}), "perceptual_hash": "8000000000000000", "difference_hash": "0000000000000000"}
            db.add(second_media)
        categories = [*CATEGORIES.keys(), "no_answer", "interference_filter"]
        created = 0
        for category in categories:
            for variant in range(8):
                name = f"Task25B_controlled_{category}_{variant + 1:02d}"
                existing_case = db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name))
                if existing_case:
                    if category == "no_answer":
                        existing_case.query_text = f"Task25B 不存在型号 XYZ-{variant} 的未收录告警"
                    elif category == "interference_filter":
                        existing_case.query_text = f"SUN2000-100KTL-M2 型号范围 variant {variant}"
                    else:
                        existing_case.query_text = f"Task25B {category} SUN2000-100KTL-M2 2064 variant {variant}"
                    db.add(existing_case)
                    continue
                if category == "no_answer":
                    expected_docs, expected_chunks, query = [], [], f"Task25B 不存在型号 XYZ-{variant} 的未收录告警"
                elif category == "interference_filter":
                    doc, chunk = evidence["device_model_query"]
                    expected_docs, expected_chunks, query = [str(doc.id)], [str(chunk.id)], f"SUN2000-100KTL-M2 型号范围 variant {variant}"
                else:
                    doc, chunk = evidence[category]
                    expected_docs, expected_chunks = [str(doc.id)], [str(chunk.id)]
                    query = f"Task25B {category} SUN2000-100KTL-M2 2064 variant {variant}"
                split = "train" if variant < 4 else "dev" if variant < 6 else "test"
                db.add(RetrievalEvaluationCase(
                    name=name, category=category, query_text=query,
                    query_media_id=media.id if category in {"image_ocr_query", "image_visual_descriptor_query", "similar_history_case"} else None,
                    expected_document_ids=expected_docs, expected_chunk_ids=expected_chunks,
                    expected_media_ids=[str(media.id)] if category == "similar_history_case" else [],
                    required_filters={"manufacturer": "huawei", "product_series": "SUN2000", "device_type": "pv_inverter"},
                    excluded_document_ids=[str(interference[0].id)], difficulty="medium", dataset_split=split,
                    review_status="engineering_verified", source_type="engineering_controlled",
                    metadata_json={"dataset_version": "task25b-v1", "engineering_verified": True},
                    created_by=user.id, reviewed_by=user.id,
                ))
                created += 1
        formal_chunks = list(db.execute(
            select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
                KnowledgeDocument.review_status == "approved", KnowledgeDocument.status == "active",
                KnowledgeDocument.parse_status == "parsed", KnowledgeChunk.status == "active",
                ~KnowledgeDocument.title.startswith("Task25B_"),
            ).order_by(KnowledgeDocument.created_at).limit(30)
        ).all())
        domain_created = 0
        if formal_chunks:
            for index in range(30):
                chunk, document = formal_chunks[index % len(formal_chunks)]
                name = f"Task25B_domain_draft_{index + 1:02d}"
                if db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name)):
                    continue
                db.add(RetrievalEvaluationCase(
                    name=name, category="competition_domain_draft", query_text=f"{document.title} {chunk.section_title or ''}"[:2000],
                    expected_document_ids=[str(document.id)], expected_chunk_ids=[str(chunk.id)], expected_media_ids=[],
                    required_filters={"manufacturer": document.manufacturer, "product_series": document.product_series,
                                      "device_type": document.device_type, "document_type": document.document_type},
                    excluded_document_ids=[], difficulty="medium", dataset_split=("train", "dev", "test")[index % 3],
                    review_status="draft", source_type="competition_domain_draft",
                    metadata_json={"review_required": True, "expert_verified": False, "dataset_version": "task25b-domain-draft-v1"},
                    created_by=user.id,
                ))
                domain_created += 1
        db.commit()
        controlled_count = len(list(db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.source_type == "engineering_controlled"))))
        domain_count = len(list(db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.source_type == "competition_domain_draft"))))
    result = {"status": "PASSED" if controlled_count >= 80 and domain_count >= 30 else "PARTIAL",
              "controlled_cases": controlled_count, "domain_draft_cases": domain_count,
              "created_controlled": created, "created_domain_draft": domain_created,
              "full_reindex_performed": False, "expert_verified_domain_drafts": 0}
    write_result("benchmark_seed.json", result)
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
