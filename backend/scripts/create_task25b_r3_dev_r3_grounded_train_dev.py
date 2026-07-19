from __future__ import annotations

import hashlib
from collections import defaultdict

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from task25b_r3_dev_r3_common import SEMANTIC_VERSION, now_iso, normalized, text_hash, write_json


DATASET = "task25b_r3_dev_r3_grounded_train_dev_v1"

COMPONENT_RULES = (
    ("通信链路", ("通信", "rs485", "modbus", "以太网", "网线", "网络", "地址")),
    ("直流侧与组串", ("直流", "组串", "光伏", "mc4", "绝缘")),
    ("交流侧与电网", ("交流", "电网", "并网", "电压", "频率")),
    ("散热与风扇", ("风扇", "散热", "温度", "过温")),
    ("储能连接", ("电池", "储能", "bat", "soc")),
    ("接地与防护", ("接地", "防护", "触电", "危险", "警告", "安全")),
    ("安装与接线", ("安装", "接线", "端子", "线缆", "连接器")),
)
ACTION_RULES = (
    ("检查", ("检查", "核查", "确认")),
    ("测量", ("测量", "检测", "测试")),
    ("设置", ("设置", "配置", "参数")),
    ("隔离", ("断开", "隔离", "关机", "禁止")),
    ("更换或修复", ("更换", "紧固", "清洁", "修复")),
)


def _detect(content: str) -> tuple[list[str], list[str], list[str]]:
    lower = content.lower()
    components = [name for name, needles in COMPONENT_RULES if any(needle in lower for needle in needles)]
    actions = [name for name, needles in ACTION_RULES if any(needle in lower for needle in needles)]
    themes = []
    if any(term in lower for term in ("通信", "rs485", "modbus", "网络", "以太网")):
        themes.append("communication")
    if any(term in lower for term in ("警告", "危险", "禁止", "防护", "接地", "触电")):
        themes.append("safety")
    if any(term in lower for term in ("告警", "故障", "异常", "失效", "中断")):
        themes.append("fault")
    return components[:2], actions[:2], themes


def _semantic_query(components: list[str], actions: list[str], themes: list[str]) -> str:
    component = components[0]
    action = actions[0]
    if "communication" in themes:
        return f"监控链路出现间歇异常时，围绕{component}应优先开展哪类{action}和复核？"
    if "safety" in themes:
        return f"处理{component}相关现场问题前，作业人员应如何完成{action}与安全确认？"
    if "fault" in themes:
        return f"设备运行异常时，围绕{component}应先采取哪类{action}步骤？"
    return f"检修{component}相关问题时，现场应如何完成{action}并确认处理条件？"


def _model_query(model: str) -> str:
    return f"{model} 设备出现运行异常时，维护前应优先查看哪些现场检查要求？"


def _fault_query(components: list[str], actions: list[str]) -> str:
    return f"出现设备故障或告警现象后，围绕{components[0]}应优先执行哪类{actions[0]}？"


def _case_payload(
    *, name: str, query: str, chunk: KnowledgeChunk, document: KnowledgeDocument, split: str,
    category: str, vector_heavy: bool, model_case: bool = False, alarm_case: bool = False,
) -> dict:
    components, actions, themes = _detect(chunk.content)
    evidence = {
        "source_chunk_id": str(chunk.id), "source_document_id": str(document.id),
        "source_content_hash": text_hash(chunk.content), "components": components, "actions": actions,
        "themes": themes, "source_locator": {"page_number": chunk.page_number, "section_title": chunk.section_title},
        "generation": "deterministic_source_only", "benchmark_query_used": False,
    }
    return {
        "name": name, "category": category, "query_text": query, "expected_document_ids": [str(document.id)],
        "expected_chunk_ids": [str(chunk.id)], "expected_media_ids": [], "required_filters": {
            "manufacturer": document.manufacturer, "product_series": document.product_series,
            "document_type": document.document_type,
        }, "excluded_document_ids": [], "difficulty": "hard", "dataset_split": split,
        "review_status": "draft", "source_type": "engineering_candidate", "metadata_json": {
            "dataset_version": DATASET, "is_vector_heavy": vector_heavy, "is_model_case": model_case,
            "is_alarm_case": alarm_case, "is_no_answer": False, "relevance_cardinality": 1,
            "grounding_status": "GROUNDED_STRONG", "grounding_evidence": evidence,
            "semantic_representation_version": SEMANTIC_VERSION, "expert_verified": False,
        },
    }


def _no_answer_payload(index: int, split: str) -> dict:
    query = (
        "船用推进器润滑油压力波动时，应如何校准喷油控制器？"
        if index % 2 else "风力机液压变桨系统失压后，应如何复位控制阀？"
    )
    return {
        "name": f"r3_no_answer_{index:02d}", "category": "no_answer", "query_text": query,
        "expected_document_ids": [], "expected_chunk_ids": [], "expected_media_ids": [], "required_filters": {},
        "excluded_document_ids": [], "difficulty": "hard", "dataset_split": split, "review_status": "draft",
        "source_type": "engineering_candidate", "metadata_json": {
            "dataset_version": DATASET, "is_vector_heavy": False, "is_model_case": False,
            "is_alarm_case": False, "is_no_answer": True, "relevance_cardinality": 0,
            "grounding_status": "QUERY_NOT_ANSWERABLE", "expert_verified": False,
        },
    }


def main() -> None:
    with SessionLocal() as db:
        existing = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET
        )))
        if existing:
            payload = {"generated_at": now_iso(), "dataset": DATASET, "status": "EXISTS_READ_ONLY", "case_count": len(existing)}
            write_json("grounded_train_dev_manifest.json", payload)
            print(payload)
            return
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        rows = list(db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.id.in_(scope.allowed_document_ids), KnowledgeChunk.status == "active",
        )))
        candidates = []
        by_bucket: dict[str, list[tuple[KnowledgeChunk, KnowledgeDocument, list[str], list[str], list[str]]]] = defaultdict(list)
        for chunk, document in rows:
            components, actions, themes = _detect(chunk.content)
            if not components or not actions or len(normalized(chunk.content)) < 80:
                continue
            item = (chunk, document, components, actions, themes)
            candidates.append(item)
            for theme in themes:
                by_bucket[theme].append(item)
        candidates.sort(key=lambda item: hashlib.sha256(str(item[0].id).encode()).hexdigest())
        semantic = []
        used_chunks: set[str] = set()
        # Reserve enough communication/safety cases before filling the semantically diverse pool.
        for theme, target in (("communication", 8), ("safety", 8)):
            for item in by_bucket[theme]:
                if len([value for value in semantic if theme in value[4]]) >= target:
                    break
                if str(item[0].id) not in used_chunks:
                    semantic.append(item); used_chunks.add(str(item[0].id))
        for item in candidates:
            if len(semantic) >= 48:
                break
            if str(item[0].id) not in used_chunks:
                semantic.append(item); used_chunks.add(str(item[0].id))
        model_sources = [(chunk, document) for chunk, document in rows if document.model and len(normalized(chunk.content)) >= 80][:4]
        fault_sources = [item for item in candidates if "fault" in item[4]][:4]
        if len(semantic) < 48 or len(model_sources) < 4 or len(fault_sources) < 4:
            raise SystemExit({"semantic": len(semantic), "models": len(model_sources), "faults": len(fault_sources)})
        records = []
        for index, (chunk, document, components, actions, themes) in enumerate(semantic, start=1):
            split = "train" if index <= 36 else "dev"
            records.append(_case_payload(
                name=f"r3_semantic_{index:03d}", query=_semantic_query(components, actions, themes), chunk=chunk,
                document=document, split=split, category="semantic_vector_heavy", vector_heavy=True,
            ))
        for index, (chunk, document) in enumerate(model_sources, start=1):
            records.append(_case_payload(
                name=f"r3_model_{index:02d}", query=_model_query(document.model), chunk=chunk, document=document,
                split="train" if index <= 3 else "dev", category="device_model_query", vector_heavy=False, model_case=True,
            ))
        for index, (chunk, document, components, actions, themes) in enumerate(fault_sources, start=1):
            records.append(_case_payload(
                name=f"r3_fault_{index:02d}", query=_fault_query(components, actions), chunk=chunk, document=document,
                split="train" if index <= 3 else "dev", category="fault_symptom", vector_heavy=False, alarm_case=True,
            ))
        for index in range(1, 5):
            records.append(_no_answer_payload(index, "train" if index <= 3 else "dev"))
        for record in records:
            db.add(RetrievalEvaluationCase(**record))
        db.commit()
        manifest = {
            "generated_at": now_iso(), "dataset": DATASET, "case_count": len(records), "splits": {
                split: sum(record["dataset_split"] == split for record in records) for split in ("train", "dev")
            }, "vector_heavy": sum(record["metadata_json"]["is_vector_heavy"] for record in records),
            "model": sum(record["metadata_json"]["is_model_case"] for record in records),
            "alarm_fault": sum(record["metadata_json"]["is_alarm_case"] for record in records),
            "no_answer": sum(record["metadata_json"]["is_no_answer"] for record in records),
            "source_only": True, "test_v3_used": False, "expert_verified": False,
        }
    write_json("grounded_train_dev_manifest.json", manifest)
    print(manifest)


if __name__ == "__main__":
    main()
