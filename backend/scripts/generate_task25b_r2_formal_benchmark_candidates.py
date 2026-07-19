from __future__ import annotations

import hashlib
import json
import re
from itertools import cycle

from sqlalchemy import func, select

from task25b_r2_common import RUNTIME, now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase


CATEGORIES = [
    "device_model_query", "fault_code_query", "symptom_query", "colloquial_symptom",
    "synonym_rewrite", "symptom_to_cause", "symptom_to_steps", "safety_procedure",
    "tools_parts", "manual_section", "historical_case", "multimodal_descriptor",
]

TEMPLATES = [
    "{maker}这类设备在{topic}场景下应查阅哪一部分资料？",
    "现场出现与{topic}相关的告警，怎样定位对应说明？",
    "设备表现为{topic}，优先需要核对哪些证据？",
    "机器有点像{topic}这种情况，维修人员先看哪里？",
    "不用原手册术语描述{topic}时，应该匹配哪段检修知识？",
    "从{topic}这一症状推断可能原因时，应引用什么资料？",
    "针对{topic}，规范的逐步排查顺序是什么？",
    "处理{topic}之前有哪些电气安全事项必须确认？",
    "排查{topic}通常需要准备哪些工具或备件？",
    "如何在手册中定位{topic}对应的章节？",
    "历史上与{topic}相似的故障案例应如何匹配？",
    "看到铭牌或面板呈现{topic}特征时，应关联哪份手册证据？",
]


def _topic(chunk: KnowledgeChunk) -> str:
    title = " ".join((chunk.section_title or "").split())
    if title:
        return title[:36]
    text = re.sub(r"\s+", " ", chunk.content or "").strip()
    text = re.sub(r"[A-Za-z]*\d{2,}[A-Za-z0-9-]*", "该型号", text)
    return (text[:36] or "异常运行")


def main() -> int:
    selection = json.loads((RUNTIME / "pilot_document_selection.json").read_text(encoding="utf-8"))
    document_ids = [item["document_id"] for item in selection.get("selected_documents") or []]
    created = 0
    existing = 0
    category_counts: dict[str, int] = {}
    with SessionLocal() as db:
        chunks = list(
            db.scalars(
                select(KnowledgeChunk)
                .join(KnowledgeDocument)
                .where(
                    KnowledgeDocument.id.in_(document_ids),
                    KnowledgeDocument.review_status == "approved",
                    KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.status == "active",
                    KnowledgeChunk.status == "active",
                )
                .order_by(KnowledgeDocument.id, KnowledgeChunk.chunk_index)
            )
        )
        for chunk in chunks:
            document = db.get(KnowledgeDocument, chunk.document_id)
            topic = _topic(chunk)
            maker = "华为" if document and document.manufacturer == "huawei" else "阳光电源"
            for index, (category, template) in enumerate(zip(CATEGORIES, TEMPLATES, strict=True), 1):
                name = f"Task25BR2_formal_{chunk.id.hex[:12]}_{index:02d}"
                if db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name)):
                    existing += 1
                    continue
                query = template.format(maker=maker, topic=topic)
                vector_heavy = category in {"colloquial_symptom", "synonym_rewrite", "symptom_to_cause", "multimodal_descriptor"}
                metadata = {
                    "generation_source": "formal_approved_chunk_rule_candidates_v1",
                    "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                    "vector_heavy": vector_heavy,
                    "lexical_easy": category in {"device_model_query", "fault_code_query", "manual_section"},
                    "hard_negative": False,
                    "source_locator": {"document_id": str(chunk.document_id), "chunk_id": str(chunk.id), "chunk_index": chunk.chunk_index},
                    "second_review_required": True,
                    "candidate_quality": "requires_human_expert_review",
                }
                db.add(RetrievalEvaluationCase(
                    name=name, category=category, query_text=query,
                    expected_document_ids=[str(chunk.document_id)], expected_chunk_ids=[str(chunk.id)],
                    expected_media_ids=[], required_filters={"device_type": "pv_inverter"}, excluded_document_ids=[],
                    difficulty="hard" if vector_heavy else "medium", dataset_split="expert_review_pool",
                    review_status="draft", source_type="task25b_r2_formal_pilot", metadata_json=metadata,
                ))
                created += 1
                category_counts[category] = category_counts.get(category, 0) + 1
        no_answer_topics = [
            "不存在的光伏逆变器型号 ZX-UNKNOWN", "虚构告警码 ALM-99999", "车用发动机机油压力",
            "燃煤锅炉燃烧器", "风力机齿轮箱", "水电机组导叶", "核电反应堆控制棒",
            "办公打印机卡纸", "家用冰箱制冷剂", "电动摩托车控制器", "未收录厂商的未知协议",
            "相互矛盾的并网电压描述", "已归档文档中的旧结论", "pending 文档中的未审核步骤",
            "不存在的部件名称", "无法确认厂商的泛化故障", "无任何设备上下文的随机代码", "被删除资料的引用请求",
        ]
        for index, topic in enumerate(no_answer_topics, 1):
            name = f"Task25BR2_no_answer_{index:03d}"
            if db.scalar(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.name == name)):
                existing += 1
                continue
            query = f"请从正式 Pilot 知识中回答：{topic}应该如何检修？"
            db.add(RetrievalEvaluationCase(
                name=name, category="no_answer", query_text=query,
                expected_document_ids=[], expected_chunk_ids=[], expected_media_ids=[], required_filters={},
                excluded_document_ids=document_ids, difficulty="hard", dataset_split="expert_review_pool",
                review_status="draft", source_type="task25b_r2_formal_pilot",
                metadata_json={
                    "generation_source": "formal_scope_hard_negative_v1",
                    "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                    "vector_heavy": False, "lexical_easy": False, "hard_negative": True,
                    "source_locator": {"policy": "formal_pilot_scope_boundary"},
                    "second_review_required": True, "candidate_quality": "requires_human_expert_review",
                },
            ))
            created += 1
            category_counts["no_answer"] = category_counts.get("no_answer", 0) + 1
        db.commit()
        total = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.source_type == "task25b_r2_formal_pilot"
        )) or 0)

    payload = {
        "status": "CANDIDATES_READY_EXPERT_REVIEW",
        "generated_at": now_iso(), "source_documents": len(document_ids), "source_chunks": len(chunks),
        "created": created, "existing": existing, "total_candidates": total,
        "target_minimum": 120, "minimum_achieved": total >= 120,
        "review_status": "draft", "expert_verified_written": 0,
        "categories_created": category_counts, "full_text_in_report": False,
        "formal_corpus_minimum_achieved": bool((selection.get("summary") or {}).get("minimum_achieved")),
    }
    write_json("formal_benchmark_candidates.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
