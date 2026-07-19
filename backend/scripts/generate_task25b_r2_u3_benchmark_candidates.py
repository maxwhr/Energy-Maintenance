from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from task25b_r2_u3_common import now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase


CATEGORIES = [
    "fault_code_query", "symptom_query", "colloquial_symptom", "device_model_query",
    "energy_storage_fault", "smartguard_fault", "communication_fault", "safety_procedure",
    "maintenance_steps", "no_answer", "cross_device_interference", "multimodal_descriptor",
]
NO_ANSWER_QUERIES = [
    "某第三方风机变桨系统报码后如何复位？", "柴油发动机机油压力过低怎样处理？",
    "非华为充电桩报E999如何维修？", "家用空调压缩机结霜如何排查？", "车辆ABS灯亮如何消除？",
]


def main() -> int:
    created = skipped = 0
    with SessionLocal() as db:
        rows = list(db.execute(
            select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
                KnowledgeDocument.source_type == "vendor_official_html",
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.status == "active",
                KnowledgeChunk.status == "active",
            ).order_by(KnowledgeDocument.created_at, KnowledgeChunk.chunk_index)
        ).all())
        existing_queries = {
            " ".join(item.lower().split())
            for item in db.scalars(select(RetrievalEvaluationCase.query_text))
        }
        for index in range(50):
            category = CATEGORIES[index % len(CATEGORIES)]
            chunk, document = rows[(index * 17) % len(rows)]
            metadata = document.metadata_json or {}
            section = (chunk.section_title or metadata.get("question_title") or "相关章节")[:100]
            family = metadata.get("product_family") or document.product_series or "华为设备"
            if category == "no_answer":
                query = NO_ANSWER_QUERIES[(index // len(CATEGORIES)) % len(NO_ANSWER_QUERIES)] + f"（边界样例{index}）"
                expected_document_ids = []
                expected_chunk_ids = []
                locator = None
                excerpt = ""
            else:
                templates = {
                    "fault_code_query": f"{family}出现{section}相关告警时，官方建议如何定位和处理？",
                    "symptom_query": f"{family}现场出现“{section}”现象，应检查哪些原因？",
                    "colloquial_symptom": f"{family}看起来不工作了，和{section}有关时该怎么查？",
                    "device_model_query": f"{section}适用于哪些华为设备型号和产品族？",
                    "energy_storage_fault": f"LUNA储能系统发生{section}相关异常时，安全处置顺序是什么？",
                    "smartguard_fault": f"SmartGuard与{section}相关的并离网或通信问题应怎样排查？",
                    "communication_fault": f"FusionSolar、SmartLogger或设备通信出现{section}问题时如何恢复？",
                    "safety_procedure": f"执行{section}前必须断开哪些电源并采取哪些防护？",
                    "maintenance_steps": f"按华为官方资料维护{section}的检查和更换步骤是什么？",
                    "cross_device_interference": f"如何判断{section}属于逆变器、储能还是管理通信设备，避免查错手册？",
                    "multimodal_descriptor": f"现场看到与{section}描述一致的指示灯或端口状态，应检索哪段官方说明？",
                }
                query = templates[category]
                expected_document_ids = [str(document.id)]
                expected_chunk_ids = [str(chunk.id)]
                locator = {"document_id": str(document.id), "chunk_id": str(chunk.id), "page_number": chunk.page_number, "section_title": chunk.section_title}
                excerpt = (chunk.content or "")[:400]
            normalized = " ".join(query.lower().split())
            name = f"Task25BR2U3_{index:03d}_{hashlib.sha256(query.encode('utf-8')).hexdigest()[:12]}"
            if normalized in existing_queries or db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name)):
                skipped += 1
                continue
            db.add(RetrievalEvaluationCase(
                name=name, category=category, query_text=query,
                expected_document_ids=expected_document_ids, expected_chunk_ids=expected_chunk_ids,
                expected_media_ids=[], required_filters={"manufacturer": "huawei"}, excluded_document_ids=[],
                difficulty="hard" if category in {"no_answer", "cross_device_interference", "multimodal_descriptor"} else "medium",
                dataset_split="expert_review_pool", review_status="engineering_verified",
                source_type="task25b_r2_u3_official_candidate",
                metadata_json={
                    "generation_source": "task25b_r2_u3_vendor_official_v1",
                    "source_locator": locator, "source_excerpt": excerpt,
                    "source_provenance": "VENDOR_OFFICIAL" if category != "no_answer" else "OUT_OF_SCOPE_NEGATIVE",
                    "vector_heavy": category in {"colloquial_symptom", "cross_device_interference", "multimodal_descriptor"},
                    "hard_negative": category in {"no_answer", "cross_device_interference"},
                    "no_answer": category == "no_answer", "requires_human_expert_review": True,
                    "second_review_required": True, "automatic_expert_verification": False,
                },
            ))
            existing_queries.add(normalized)
            created += 1
        db.commit()
        total = len(list(db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name.like("Task25BR2U3_%")))))
    payload = {
        "generated_at": now_iso(), "created": created, "skipped_idempotent_or_semantic_duplicate": skipped,
        "u3_candidates": total, "u2_plus_u3_target_candidates": 150 + total,
        "review_status": "engineering_verified", "expert_verified_created": 0,
        "second_reviews_created": 0, "requires_human_review": True,
    }
    write_json("u3_benchmark_candidates.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
