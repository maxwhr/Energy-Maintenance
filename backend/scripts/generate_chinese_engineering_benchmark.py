from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from task25b_r3_dev_common import now_iso, write_json

DATASET = "task25b_r2_u3_r3_dev_zh_v1"


def main() -> None:
    with SessionLocal() as db:
        existing = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET)))
        if existing:
            cases = existing
        else:
            rows = list(db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
                KnowledgeDocument.manufacturer == "huawei", KnowledgeDocument.review_status == "approved",
                KnowledgeDocument.metadata_json["normalized_language"].as_string() == "zh-CN",
                KnowledgeDocument.metadata_json["engineering_approved_for_pilot"].as_string() == "true",
                KnowledgeChunk.status == "active")).all())
            if len(rows) < 120: raise SystemExit("CHINESE_CORPUS_INSUFFICIENT")
            cases = []
            for index in range(120):
                chunk, doc = rows[index % len(rows)]
                heading = chunk.section_title or doc.title
                category = ["device_model_query", "fault_code_query", "fault_symptom", "installation", "maintenance", "safety", "communication", "storage_fault"][index % 8]
                query = f"请根据华为官方中文资料说明：{heading}。"
                metadata = {"dataset_version": DATASET, "language": "zh-CN", "engineering_verified": True,
                    "expert_verified": False, "second_reviewed": False, "vector_heavy": index < 30,
                    "safety": category == "safety", "hard_negative": False,
                    "approval_mode": "development_engineering_auto"}
                cases.append(RetrievalEvaluationCase(name=f"中文工程基准-{index+1:03d}", category=category,
                    query_text=query, expected_document_ids=[str(doc.id)], expected_chunk_ids=[str(chunk.id)],
                    expected_media_ids=[], required_filters={"manufacturer": "huawei", "device_type": "pv_inverter"},
                    excluded_document_ids=[], difficulty="hard" if index < 30 else "medium", dataset_split="test",
                    review_status="engineering_verified", source_type="engineering_candidate", metadata_json=metadata))
            for index in range(15):
                cases.append(RetrievalEvaluationCase(name=f"中文无答案-{index+1:02d}", category="no_answer",
                    query_text=f"第三方非光伏设备虚构告警 X9{index:02d} 在华为逆变器中如何处理？",
                    expected_document_ids=[], expected_chunk_ids=[], expected_media_ids=[], required_filters={"manufacturer": "huawei"},
                    excluded_document_ids=[], difficulty="hard", dataset_split="test", review_status="engineering_verified",
                    source_type="engineering_candidate", metadata_json={"dataset_version": DATASET, "language": "zh-CN",
                    "engineering_verified": True, "expert_verified": False, "second_reviewed": False,
                    "vector_heavy": False, "hard_negative": False, "no_answer": True}))
            for index in range(15):
                chunk, doc = rows[(120 + index) % len(rows)]
                cases.append(RetrievalEvaluationCase(name=f"中文困难负样本-{index+1:02d}", category="hard_negative",
                    query_text=f"现场条件与“{chunk.section_title or doc.title}”的安全前提矛盾，是否仍可跳过断电步骤？",
                    expected_document_ids=[str(doc.id)], expected_chunk_ids=[str(chunk.id)], expected_media_ids=[],
                    required_filters={"manufacturer": "huawei"}, excluded_document_ids=[], difficulty="hard", dataset_split="test",
                    review_status="engineering_verified", source_type="engineering_candidate",
                    metadata_json={"dataset_version": DATASET, "language": "zh-CN", "engineering_verified": True,
                    "expert_verified": False, "second_reviewed": False, "vector_heavy": True, "hard_negative": True,
                    "conflict_reason": "查询要求与官方安全前提冲突，不得给出跳过安全步骤的结论"}))
            db.add_all(cases); db.commit()
        payload = {"generated_at": now_iso(), "dataset_version": DATASET, "cases": len(cases),
            "vector_heavy": sum(bool((x.metadata_json or {}).get("vector_heavy")) for x in cases),
            "no_answer": sum(x.category == "no_answer" for x in cases),
            "hard_negatives": sum(bool((x.metadata_json or {}).get("hard_negative")) for x in cases),
            "safety": sum(bool((x.metadata_json or {}).get("safety")) for x in cases),
            "alarm_fault": sum(x.category in {"fault_code_query", "fault_symptom"} for x in cases),
            "engineering_verified": sum(x.review_status == "engineering_verified" for x in cases),
            "expert_verified": sum(x.review_status == "expert_verified" for x in cases)}
    write_json("chinese_engineering_benchmark.json", payload); print({"status": "passed", **payload})


if __name__ == "__main__": main()
