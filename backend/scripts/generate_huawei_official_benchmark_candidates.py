from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select

from task25b_r2_u2_common import now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase


CATEGORIES = [
    "device_model_query", "fault_code_query", "symptom_query", "installation_steps",
    "maintenance_steps", "safety_procedure", "tools_parts", "parameter_range",
    "communication_fault", "grid_connection_fault", "low_insulation_resistance",
    "arc_fault", "over_temperature", "energy_storage_fault", "module_controller_fault",
]


def main() -> int:
    created = skipped = 0
    with SessionLocal() as db:
        rows = list(db.execute(
            select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
                KnowledgeDocument.source_type == "vendor_official",
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.status == "active",
                KnowledgeChunk.status == "active",
            ).order_by(KnowledgeDocument.created_at, KnowledgeChunk.chunk_index)
        ).all())
        source_document_count = len({str(item[1].id) for item in rows})
        source_chunk_count = len(rows)
        for index in range(min(150, len(rows) * 2)):
            chunk, document = rows[index % len(rows)]
            category = CATEGORIES[index % len(CATEGORIES)]
            name = f"Task25BR2U2_{str(chunk.id).replace('-', '')[:12]}_{index:03d}"
            if db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name)):
                skipped += 1
                continue
            section = (chunk.section_title or "相关章节")[:80]
            query = {
                "device_model_query": f"这份华为官方资料中，{section}适用于哪些设备型号？",
                "fault_code_query": f"遇到{section}相关告警时，应如何定位官方说明？",
                "installation_steps": f"按照华为官方资料，{section}的安装步骤和前置检查是什么？",
                "maintenance_steps": f"现场维护{section}时应按什么顺序操作？",
                "safety_procedure": f"处理{section}之前必须遵守哪些安全警告？",
                "tools_parts": f"执行{section}需要哪些工具、连接件或备件？",
            }.get(category, f"设备出现与{section}相关的现象时，应查阅哪段华为官方技术资料？")
            query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
            db.add(RetrievalEvaluationCase(
                name=name, category=category, query_text=query,
                expected_document_ids=[str(document.id)], expected_chunk_ids=[str(chunk.id)],
                expected_media_ids=[], required_filters={"manufacturer": "huawei", "device_type": "pv_inverter"},
                excluded_document_ids=[], difficulty="medium", dataset_split="expert_review_pool",
                review_status="engineering_verified", source_type="task25b_r2_formal_pilot",
                metadata_json={
                    "generation_source": "huawei_vendor_official_parsed_chunks_v1",
                    "machine_review_status": "engineering_verified", "query_sha256": query_hash,
                    "vector_heavy": category in {"symptom_query", "communication_fault", "low_insulation_resistance", "arc_fault"},
                    "lexical_easy": category in {"device_model_query", "fault_code_query"},
                    "hard_negative": False, "source_provenance": "VENDOR_OFFICIAL",
                    "source_locator": {
                        "document_id": str(document.id), "chunk_id": str(chunk.id),
                        "page_number": chunk.page_number, "section_title": chunk.section_title,
                    },
                    "source_excerpt": (chunk.content or "")[:400],
                    "document_review_status": document.review_status,
                    "requires_human_expert_review": True, "second_review_required": True,
                },
            ))
            created += 1
        db.commit()
        total = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.name.like("Task25BR2U2_%")
        )) or 0)
    payload = {
        "generated_at": now_iso(), "source_documents": source_document_count,
        "source_chunks": source_chunk_count, "created": created, "skipped_idempotent": skipped,
        "total_candidates": total, "machine_status": "engineering_verified",
        "expert_verified_created": 0, "requires_human_review": True,
    }
    write_json("huawei_benchmark_candidates.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
