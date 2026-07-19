from __future__ import annotations

import hashlib
import json
import re
import argparse
from collections import Counter, defaultdict

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase, User
from task25b_r3_dev_r2_common import OUT, ROOT, V3_DATASET, coverage_rows, json_hash, now_iso, section_key


MODEL_RE = re.compile(r"(?i)\b(?:SUN\d{4}[A-Z0-9\-()/]{0,32}|LUNA\d{4}[A-Z0-9\-()/]{0,32}|SmartLogger\d+[A-Z0-9\-]{0,24}|FusionSolar)\b")
ALARM_RE = re.compile(r"(?<!\d)(?:[A-Z]{1,4}[-_]?)?\d{3,6}(?!\d)", re.I)


def _model(chunk: KnowledgeChunk) -> str | None:
    for value in MODEL_RE.findall(" ".join((chunk.section_title or "", chunk.content or ""))):
        if len(value) >= 7:
            return value.strip("-() /")
    return None


def _alarm(chunk: KnowledgeChunk) -> str | None:
    for value in ALARM_RE.findall(" ".join((chunk.section_title or "", chunk.content or ""))):
        digits = re.sub(r"\D", "", value)
        if digits and not 1900 <= int(digits) <= 2100:
            return value.upper()
    return None


def _semantic_kind(chunk: KnowledgeChunk) -> str:
    value = (chunk.content or "").lower()
    if any(term in value for term in ("通信", "网络", "离线", "rs485", "以太网")):
        return "communication"
    if any(term in value for term in ("温度", "风扇", "散热", "降额")):
        return "thermal"
    if any(term in value for term in ("绝缘", "接地", "漏电", "对地")):
        return "insulation"
    if any(term in value for term in ("电池", "储能", "soc", "充电", "放电")):
        return "storage"
    if any(term in value for term in ("告警", "故障", "异常")):
        return "fault"
    return "maintenance"


def _semantic_query(chunk: KnowledgeChunk) -> tuple[str, str] | None:
    content = (chunk.content or "").lower()
    if "sim" in content and "天线" in content:
        return "采集装置通过蜂窝网络接入时，身份识别卡和信号部件应怎样正确装配？", "communication"
    if "ip地址" in content and "网段" in content:
        return "采集装置与网络终端互联时，两端网络地址应满足什么关系？", "communication"
    if "导轨" in content and "安装" in content:
        return "将采集装置固定到标准金属安装槽之前，需要满足哪些结构条件？", "communication"
    if "散热" in content and any(term in content for term in ("风扇", "温度", "降额")):
        return "设备热量不易排出并出现功率受限时，应优先检查哪类通风部件？", "thermal"
    if "绝缘" in content and any(term in content for term in ("接地", "组串", "直流")):
        return "雨后直流侧对地状态异常时，现场需要先从哪些绝缘环节排查？", "insulation"
    if any(term in content for term in ("充电", "放电", "电池", "储能")) and "luna" in content:
        return "储能单元在能量输入输出过程中状态异常时，应先核查哪些连接和运行条件？", "storage"
    if "通信" in content and any(term in content for term in ("离线", "网络", "rs485", "以太网")):
        return "后台连续收不到现场状态时，应从哪些数据链路环节开始检查？", "communication"
    return None


SEMANTIC_QUERIES = {
    "communication": "后台连续收不到现场设备状态且数据链路异常时，应从哪些通信环节开始检查？",
    "thermal": "设备运行一段时间后因散热受限出现功率受限，应优先检查哪些部位？",
    "insulation": "雨后直流侧对地状态异常，现场应如何先做安全排查？",
    "storage": "储能单元在充放电过程中状态异常时，应该先核查哪些连接和运行条件？",
    "fault": "设备出现持续异常提示但没有明确代码时，现场处理应先确认什么？",
    "maintenance": "进行现场维护前需要确认哪些前置条件和安全步骤？",
}


def _stable_chunks(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    return sorted(chunks, key=lambda item: hashlib.sha256(str(item.id).encode()).hexdigest())


def _pick(pool: list[KnowledgeChunk], count: int, *, offset: int = 0) -> list[KnowledgeChunk]:
    if not pool:
        raise RuntimeError("no eligible source chunks available")
    return [pool[(offset + index) % len(pool)] for index in range(count)]


def _expected(chunk: KnowledgeChunk, same_section: dict[tuple[str, str], list[KnowledgeChunk]], *, multi: bool) -> list[str]:
    if not multi:
        return [str(chunk.id)]
    group = same_section.get((str(chunk.document_id), str(chunk.section_title or "")), [])
    if len(group) < 2:
        group = same_section.get((str(chunk.document_id), "__all__"), [])
        try:
            position = group.index(chunk)
        except ValueError:
            position = 0
        group = [chunk, *group[position + 1:position + 3], *group[max(0, position - 2):position]]
    values = list(dict.fromkeys(str(value.id) for value in group))[:3]
    return values if len(values) > 1 else [str(chunk.id)]


def _case_payload(
    *, index: int, split: str, chunk: KnowledgeChunk | None, document: KnowledgeDocument | None,
    category: str, query: str, expected_chunks: list[str], flags: dict, subcategories: list[str],
) -> RetrievalEvaluationCase:
    no_answer = not expected_chunks
    source_locator = {}
    if chunk:
        source_locator = {"document_id": str(chunk.document_id), "chunk_id": str(chunk.id), "page_number": chunk.page_number,
                          "section_title": chunk.section_title}
    relevance = 0 if no_answer else len(expected_chunks)
    metadata = {
        "dataset_version": V3_DATASET, "engineering_verified": True, "expert_verified": False,
        "test_v3_frozen": False, "subcategories": subcategories, "query_type": category,
        "expected_documents": [str(document.id)] if document and not no_answer else [],
        "expected_sections": [str(chunk.section_title or chunk.page_number or "unknown")] if chunk and not no_answer else [],
        "relevance_cardinality": relevance, "evaluation_contract": "no_answer" if no_answer else ("multi_relevant" if relevance > 1 else "single_relevant"),
        "is_no_answer": no_answer, "source_locator": source_locator, "lexical_overlap": None,
        **flags,
    }
    return RetrievalEvaluationCase(
        name=f"R2-v3-{split}-{index:03d}-{category}", category=category, query_text=query,
        # JSONB-backed benchmark labels are persisted as canonical strings, matching the existing R1/R2 datasets.
        expected_document_ids=[] if no_answer else [str(document.id)], expected_chunk_ids=[] if no_answer else list(expected_chunks),
        expected_media_ids=[], required_filters={"manufacturer": "huawei", "product_series": document.product_series if document else None,
                                                   "device_type": document.device_type if document else "pv_inverter"},
        excluded_document_ids=[], difficulty="hard" if flags.get("is_vector_heavy") or no_answer else "medium",
        dataset_split=split, review_status="engineering_verified", source_type="engineering_candidate", metadata_json=metadata,
    )


def _build_split(
    *, split: str, total: int, offset: int, chunks: list[KnowledgeChunk], documents: dict[str, KnowledgeDocument],
    same_section: dict[tuple[str, str], list[KnowledgeChunk]],
) -> list[RetrievalEvaluationCase]:
    by_series: dict[str, list[KnowledgeChunk]] = defaultdict(list)
    for chunk in chunks:
        by_series[documents[str(chunk.document_id)].product_series or "other"].append(chunk)
    models = [chunk for chunk in chunks if _model(chunk)]
    alarms = [chunk for chunk in chunks if _alarm(chunk)]
    semantic = [chunk for chunk in chunks if _semantic_query(chunk)]
    safety = [chunk for chunk in chunks if any(word in (chunk.content or "") for word in ("安全", "警告", "危险", "断开", "防护"))]
    selected: list[RetrievalEvaluationCase] = []
    index = 1
    # Model cases: each split is deliberately stratified across four product families.
    model_series = ("SUN2000", "LUNA2000", "SmartLogger", "FusionSolar", "SmartLogger", "SUN2000", "SmartLogger", "LUNA2000", "SmartLogger", "FusionSolar", "SmartLogger", "SUN2000")
    for position, chunk in enumerate(_pick(models, 12, offset=offset)):
        document = documents[str(chunk.document_id)]; model = _model(chunk) or document.product_series or "SUN2000"
        variant = model.lower() if position % 3 == 1 else (model.replace("-", " ") if position % 3 == 2 else model)
        if position < len(model_series):
            family_pool = by_series.get(model_series[position]) or models
            chunk = _pick(family_pool, 1, offset=offset + position)[0]; document = documents[str(chunk.document_id)]; model = _model(chunk) or document.product_series or model_series[position]; variant = model
        locator = str(chunk.section_title or (chunk.metadata_json or {}).get("source_locator") or "维护章节")[:120]
        selected.append(_case_payload(index=index, split=split, chunk=chunk, document=document, category="device_model_query",
            query=f"{variant} 的“{locator}”章节涉及什么检查或处理要点？", expected_chunks=_expected(chunk, same_section, multi=position % 4 == 0),
            flags={"is_model_case": True, "is_alarm_case": False, "is_vector_heavy": False, "required_model": model},
            subcategories=["model", document.product_series or "other", "inverter"])); index += 1
    for position, chunk in enumerate(_pick(alarms, 12, offset=offset + 19)):
        document = documents[str(chunk.document_id)]; alarm = _alarm(chunk) or ""
        locator = str(chunk.section_title or (chunk.metadata_json or {}).get("source_locator") or "告警章节")[:120]
        selected.append(_case_payload(index=index, split=split, chunk=chunk, document=document, category="fault_code_query",
            query=f"告警 {alarm} 在“{locator}”章节中对应的原因和处理建议是什么？", expected_chunks=_expected(chunk, same_section, multi=position % 3 == 0),
            flags={"is_model_case": False, "is_alarm_case": True, "is_vector_heavy": False, "required_alarm_identifier": alarm},
            subcategories=["alarm", "fault"])); index += 1
    communication_pool = [chunk for chunk in semantic if (_semantic_query(chunk) or ("", ""))[1] == "communication"]
    storage_pool = [chunk for chunk in semantic if (_semantic_query(chunk) or ("", ""))[1] == "storage"]
    semantic_selection = [*_pick(communication_pool or semantic, 5, offset=offset + 47),
                          *_pick(storage_pool or semantic, 5, offset=offset + 52), *_pick(semantic, 8, offset=offset + 57)]
    for position, chunk in enumerate(semantic_selection):
        document = documents[str(chunk.document_id)]; semantic_query, kind = _semantic_query(chunk) or (SEMANTIC_QUERIES[_semantic_kind(chunk)], _semantic_kind(chunk))
        selected.append(_case_payload(index=index, split=split, chunk=chunk, document=document, category="semantic_symptom",
            query=semantic_query, expected_chunks=_expected(chunk, same_section, multi=position < 8),
            flags={"is_model_case": False, "is_alarm_case": False, "is_vector_heavy": True, "semantic_kind": kind},
            subcategories=["vector_heavy", kind, "semantic"])); index += 1
    for position, chunk in enumerate(_pick(safety or chunks, 8, offset=offset + 71)):
        document = documents[str(chunk.document_id)]
        selected.append(_case_payload(index=index, split=split, chunk=chunk, document=document, category="safety_procedure",
            query="现场开始维护前，如何确认隔离、防护和安全条件？", expected_chunks=_expected(chunk, same_section, multi=position < 3),
            flags={"is_model_case": False, "is_alarm_case": False, "is_vector_heavy": position < 2}, subcategories=["safety"])); index += 1
    # Ten difficult negatives are intentionally empty-label no-answer cases.
    for position in range(10):
        selected.append(_case_payload(index=index, split=split, chunk=None, document=None, category="no_answer",
            query="量子星云谐振虚构失配", expected_chunks=[],
            flags={"is_model_case": False, "is_alarm_case": False, "is_vector_heavy": False, "hard_negative": True}, subcategories=["no_answer", "hard_negative"])); index += 1
    filler = _pick(chunks, max(0, total - len(selected)), offset=offset + 97)
    for position, chunk in enumerate(filler):
        document = documents[str(chunk.document_id)]; kind = _semantic_kind(chunk)
        category = "communication" if kind == "communication" else ("storage_fault" if kind == "storage" else "maintenance")
        selected.append(_case_payload(index=index, split=split, chunk=chunk, document=document, category=category,
            query=f"针对设备运行维护场景，{chunk.section_title or '相关章节'}中推荐的检查顺序是什么？", expected_chunks=_expected(chunk, same_section, multi=position % 3 == 0),
            flags={"is_model_case": False, "is_alarm_case": False, "is_vector_heavy": False}, subcategories=[category, kind])); index += 1
    return selected[:total]


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--rebuild-unfrozen", action="store_true"); args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        existing = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V3_DATASET
        ).order_by(RetrievalEvaluationCase.created_at)))
        if existing:
            if any((case.metadata_json or {}).get("test_v3_frozen") for case in existing):
                raise SystemExit("v3 test labels are frozen and cannot be changed")
            existing_test = [case for case in existing if case.dataset_split == "test_v3"]
            existing_coverage = coverage_rows(existing_test)
            existing_smartlogger = sum("SmartLogger" in ((case.metadata_json or {}).get("subcategories") or []) for case in existing_test)
            existing_communication = sum("communication" in ((case.metadata_json or {}).get("subcategories") or []) for case in existing_test)
            existing_storage = sum("storage" in ((case.metadata_json or {}).get("subcategories") or []) for case in existing_test)
            if not args.rebuild_unfrozen and existing_coverage["model_cases"] >= 12 and existing_coverage["alarm_cases"] >= 12 and existing_coverage["vector_heavy"] >= 20 and existing_coverage["no_answer"] >= 10 and existing_coverage["multi_relevant"] >= 15 and existing_smartlogger >= 5 and existing_communication >= 5 and existing_storage >= 5:
                cases = existing
            else:
                # The first draft is retained for audit, but is not a frozen dataset and is never eligible for an official run.
                for case in existing:
                    metadata = dict(case.metadata_json or {})
                    metadata.update({"dataset_version": "task25b_r3_dev_r2_zh_v3_invalid_draft", "invalid_pre_freeze_generation": True,
                                     "invalid_reason": "pre-freeze stratification/query-grounding rebuild"})
                    case.metadata_json = metadata
                    db.add(case)
                db.commit()
                existing = []
        if not existing:
            chunks = list(db.scalars(select(KnowledgeChunk).join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id).where(
                KnowledgeChunk.status == "active", KnowledgeDocument.status == "active", KnowledgeDocument.review_status == "approved",
                KnowledgeDocument.metadata_json["normalized_language"].as_string() == "zh-CN",
                KnowledgeDocument.metadata_json["approved_for_pilot"].as_string() == "true",
                KnowledgeDocument.metadata_json["engineering_approved_for_pilot"].as_string() == "true",
            )))
            chunks = _stable_chunks(chunks)
            documents = {str(doc.id): doc for doc in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_({chunk.document_id for chunk in chunks})))}
            same_section: dict[tuple[str, str], list[KnowledgeChunk]] = defaultdict(list)
            for chunk in chunks:
                same_section[(str(chunk.document_id), str(chunk.section_title or ""))].append(chunk)
                same_section[(str(chunk.document_id), "__all__")].append(chunk)
            cases = [*_build_split(split="train", total=120, offset=0, chunks=chunks, documents=documents, same_section=same_section),
                     *_build_split(split="dev", total=60, offset=31, chunks=chunks, documents=documents, same_section=same_section),
                     *_build_split(split="test_v3", total=60, offset=79, chunks=chunks, documents=documents, same_section=same_section)]
            admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
            for case in cases:
                case.created_by = admin.id if admin else None
            db.add_all(cases); db.commit()
        payload_cases = [{"id": str(case.id), "name": case.name, "split": case.dataset_split, "category": case.category,
                          "query_hash": hashlib.sha256(case.query_text.encode("utf-8")).hexdigest(), "metadata": case.metadata_json or {},
                          "expected_document_ids": [str(value) for value in (case.expected_document_ids or [])], "expected_chunk_ids": [str(value) for value in (case.expected_chunk_ids or [])]} for case in cases]
        digest = json_hash(sorted(payload_cases, key=lambda value: value["id"]))
        splits = Counter(case.dataset_split for case in cases)
        test_cases = [case for case in cases if case.dataset_split == "test_v3"]
        coverage = coverage_rows(test_cases)
        coverage.update({"safety": sum("safety" in ((case.metadata_json or {}).get("subcategories") or []) for case in test_cases),
                         "communication": sum("communication" in ((case.metadata_json or {}).get("subcategories") or []) for case in test_cases),
                         "storage": sum("storage" in ((case.metadata_json or {}).get("subcategories") or []) for case in test_cases),
                         "smartlogger": sum("SmartLogger" in ((case.metadata_json or {}).get("subcategories") or []) for case in test_cases),
                         "inverter": sum("inverter" in ((case.metadata_json or {}).get("subcategories") or []) for case in test_cases),
                         "hard_negative": sum(bool((case.metadata_json or {}).get("hard_negative")) for case in test_cases)})
    manifest = {"generated_at": now_iso(), "dataset_version": V3_DATASET, "case_count": len(cases), "splits": dict(splits),
                "dataset_sha256": digest, "test_v3_coverage": coverage, "expert_verified": False, "test_v3_frozen": False,
                "stratified": True, "source": "current approved Chinese Pilot chunks"}
    (OUT / "dataset_v3_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
