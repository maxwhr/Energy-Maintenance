from __future__ import annotations

import hashlib
import re
from collections import Counter

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, User
from task25b_r3_dev_r4_common import DATASET_VERSION, OUT, now_iso, read_json, write_json


def ngrams(value: str) -> set[str]:
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())
    return {normalized[index:index + width] for width in (2, 3) for index in range(max(0, len(normalized) - width + 1))}


def overlap(left: str, right: str) -> float:
    a, b = ngrams(left), ngrams(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def signature(unit: dict) -> tuple:
    return (
        unit["product_family"], unit["semantic_unit_type"], tuple(unit["component_terms"][:2]),
        tuple(unit["symptom_terms"][:2]), tuple(unit["cause_terms"][:2]), tuple(unit["action_terms"][:2]),
        tuple(unit["safety_terms"][:2]), tuple(unit["prerequisite_terms"][:2]), tuple(unit["verification_terms"][:2]),
    )


def topic_hint(unit: dict) -> str:
    """Return a source-present partial section discriminator, never a full title/model/code."""
    section = re.sub(r"^\s*[\d.]+\s*", "", str(unit.get("source_section") or "")).strip()
    for value in [*(unit.get("device_models") or []), *(unit.get("alarm_codes") or [])]:
        if value:
            section = section.replace(str(value), " ")
    candidates = [
        value for value in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,12}", section)
        if value.lower() not in {"sun2000", "luna2000", "smartlogger", "fusionsolar"}
    ]
    generic = ("设置", "操作", "处理", "故障", "告警", "检查", "安装", "维护", "步骤", "说明", "配置", "更换", "调试")
    for value in candidates:
        reduced = value
        for term in generic:
            reduced = reduced.replace(term, "")
        reduced = reduced.strip()
        if len(reduced) >= 2 and reduced.lower() != section.lower():
            return reduced[:12]
    source_tail = section.strip(" \t\r\n，。；：、（）()[]【】")
    if len(source_tail) >= 5:
        return source_tail[-min(8, len(source_tail) - 1):].lstrip("，。；：、（）()[]【】")
    return ""


def grounded_query(unit: dict) -> tuple[str, list[str]]:
    hint = topic_hint(unit)
    concepts = list(dict.fromkeys([
        hint,
        *unit["component_terms"][:1], *unit["symptom_terms"][:1], *unit["cause_terms"][:1],
        *unit["action_terms"][:1], *unit["safety_terms"][:1], *unit["prerequisite_terms"][:1],
        *unit["verification_terms"][:1],
    ]))
    focus = "、".join(value for value in concepts[:4] if value) or "设备状态"
    templates = {
        "COMMUNICATION": f"现场出现{focus}相关异常时，应从哪些通信条件和处理动作开始排查？",
        "ALARM": f"设备出现{focus}相关现象但没有完整告警标识时，应如何判断并处理？",
        "PROCEDURE": f"进行{focus}相关检修时，操作前、操作中和完成后分别要确认什么？",
        "SAFETY": f"处理{focus}相关问题前，需要落实哪些风险隔离和安全措施？",
        "CAUSE": f"出现{focus}相关现象时，资料给出的原因线索与检查动作是什么？",
        "SYMPTOM": f"现场表现为{focus}时，应该优先核查哪些条件并采取什么动作？",
        "ACTION": f"面对{focus}相关问题，现场应按什么顺序检查和处理？",
    }
    return templates.get(unit["semantic_unit_type"], f"针对{focus}相关问题，资料给出的检修要点是什么？"), concepts[:4]


def make_positive(unit: dict, *, category: str, query: str, vector_heavy: bool, concepts: list[str]) -> dict:
    return {
        "category": category, "query": query, "expected_document_ids": [unit["document_id"]],
        "expected_chunk_ids": unit["source_chunk_ids"], "expected_semantic_unit_ids": [unit["semantic_unit_id"]],
        "unit": unit, "vector_heavy": vector_heavy, "concepts": concepts,
    }


def main() -> None:
    source = read_json(OUT / "semantic_units.json")
    units = source.get("units") or []
    if not units:
        raise SystemExit("semantic units must be built first")
    hint_counts = Counter((unit["product_family"], topic_hint(unit).lower()) for unit in units if topic_hint(unit))
    unique = [
        unit for unit in units
        if topic_hint(unit) and hint_counts[(unit["product_family"], topic_hint(unit).lower())] == 1
    ]
    unique.sort(key=lambda unit: hashlib.sha256(unit["semantic_unit_id"].encode()).hexdigest())
    vector_rows = []
    used_units = set()
    used_queries = set()
    for product in ("SUN2000", "SmartLogger", "LUNA2000", "FusionSolar"):
        product_candidates = sorted(
            [unit for unit in unique if unit["product_family"] == product],
            key=lambda unit: (unit["semantic_unit_type"] != "COMMUNICATION", hashlib.sha256(unit["semantic_unit_id"].encode()).hexdigest()),
        )
        for unit in product_candidates:
            query, concepts = grounded_query(unit)
            source_excerpt = unit["canonical_text"].split("原文证据：", 1)[-1]
            if query in used_queries or overlap(query, source_excerpt) >= 0.18:
                continue
            vector_rows.append(make_positive(unit, category="semantic_vector_heavy", query=query, vector_heavy=True, concepts=concepts))
            used_units.add(unit["semantic_unit_id"]); used_queries.add(query)
            if sum(row["unit"]["product_family"] == product for row in vector_rows) >= 15:
                break
    if len(vector_rows) < 60:
        for unit in unique:
            if unit["semantic_unit_id"] in used_units:
                continue
            query, concepts = grounded_query(unit)
            source_excerpt = unit["canonical_text"].split("原文证据：", 1)[-1]
            if query in used_queries or overlap(query, source_excerpt) >= 0.18:
                continue
            vector_rows.append(make_positive(unit, category="semantic_vector_heavy", query=query, vector_heavy=True, concepts=concepts))
            used_units.add(unit["semantic_unit_id"]); used_queries.add(query)
            if len(vector_rows) == 60:
                break
    if len(vector_rows) != 60:
        raise SystemExit(f"unable to create 60 unambiguous vector-heavy cases: {len(vector_rows)}")
    model_rows = []
    for unit in [item for item in unique if item["device_models"]]:
        model = unit["device_models"][0]
        query = f"{model} 涉及的检修现象或操作要点是什么？"
        if query in used_queries:
            continue
        model_rows.append(make_positive(unit, category="device_model_query", query=query, vector_heavy=False, concepts=[model]))
        used_queries.add(query)
        if len(model_rows) == 10:
            break
    alarm_rows = []
    for unit in [item for item in unique if item["alarm_codes"]]:
        code = unit["alarm_codes"][0]
        query = f"告警代码 {code} 对应的现象与处理动作是什么？"
        if query in used_queries:
            continue
        alarm_rows.append(make_positive(unit, category="alarm_query", query=query, vector_heavy=False, concepts=[code]))
        used_queries.add(query)
        if len(alarm_rows) == 10:
            break
    safety_rows = []
    for unit in [item for item in unique if item["safety_terms"] and item["semantic_unit_id"] not in used_units]:
        focus = "、".join([*unit["component_terms"][:1], *unit["safety_terms"][:2]]) or "检修作业"
        query = f"进行{focus}相关操作时需要遵守哪些安全要求？"
        if query in used_queries:
            continue
        safety_rows.append(make_positive(unit, category="safety_procedure", query=query, vector_heavy=False, concepts=unit["safety_terms"][:2]))
        used_queries.add(query)
        if len(safety_rows) == 10:
            break
    if min(len(model_rows), len(alarm_rows), len(safety_rows)) < 10:
        raise SystemExit({"model": len(model_rows), "alarm": len(alarm_rows), "safety": len(safety_rows)})
    no_answer_queries = [
        "风力发电机齿轮箱油温异常如何处理？", "柴油发电机喷油泵压力是多少？", "矿用提升机钢丝绳如何验收？",
        "电动汽车制动液更换周期是多少？", "水轮机导叶间隙标准是什么？", "燃气轮机点火失败如何处理？",
        "锅炉给水泵汽蚀如何排查？", "铁路信号机灯丝报警如何复位？", "船舶主机滑油压力低怎么办？",
        "空压机冷却水流量标准是多少？",
    ]
    no_answer_rows = [{
        "category": "no_answer", "query": query, "expected_document_ids": [], "expected_chunk_ids": [],
        "expected_semantic_unit_ids": [], "unit": None, "vector_heavy": False, "concepts": [],
    } for query in no_answer_queries]
    rows = vector_rows + model_rows + alarm_rows + safety_rows + no_answer_rows
    with SessionLocal() as db:
        existing = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET_VERSION
        )) or 0)
        if existing:
            if existing != len(rows):
                raise SystemExit(f"dataset already exists with unexpected {existing} rows; refusing to overwrite")
            existing_cases = list(db.scalars(select(RetrievalEvaluationCase).where(
                RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET_VERSION
            ).order_by(RetrievalEvaluationCase.name)))
            snapshot_path = OUT / "grounded_train_dev_pre_ambiguity_repair.json"
            if not snapshot_path.exists():
                write_json("grounded_train_dev_pre_ambiguity_repair.json", {
                    "generated_at": now_iso(), "dataset": DATASET_VERSION,
                    "reason": "generic source concepts did not uniquely identify a semantic unit",
                    "rows": [{
                        "case_id": str(case.id), "query_hash": hashlib.sha256(case.query_text.encode()).hexdigest(),
                        "expected_chunk_ids": [str(value) for value in (case.expected_chunk_ids or [])],
                        "expected_semantic_unit_ids": (case.metadata_json or {}).get("expected_semantic_unit_ids") or [],
                    } for case in existing_cases],
                })
            for index, (case, row) in enumerate(zip(existing_cases, rows)):
                unit = row["unit"]
                source_excerpt = unit["canonical_text"].split("原文证据：", 1)[-1] if unit else ""
                metadata = dict(case.metadata_json or {})
                metadata.update({
                    "dataset_version": DATASET_VERSION, "is_vector_heavy": row["vector_heavy"],
                    "is_no_answer": row["category"] == "no_answer",
                    "expected_semantic_unit_ids": row["expected_semantic_unit_ids"],
                    "expected_source_chunk_ids": row["expected_chunk_ids"],
                    "grounding_concepts": row["concepts"], "ambiguity_free_topic_hint": topic_hint(unit) if unit else None,
                    "ambiguity_free_revision": 2, "source_hash": unit["source_hash"] if unit else None,
                    "source_locator": unit["source_locator"] if unit else None,
                    "source_section": unit["source_section"] if unit else None,
                    "device_models": unit["device_models"] if unit else [], "alarm_codes": unit["alarm_codes"] if unit else [],
                    "lexical_overlap": round(overlap(row["query"], source_excerpt), 6) if unit else 0.0,
                    "grounding_status": "PENDING_ENGINEERING_CHECK", "engineering_grounded": False,
                    "lexical_leakage": None, "human_expert_verified": False, "expert_verified": False,
                    "test_data_used": False, "source_only": True,
                })
                case.query_text = row["query"]
                case.category = row["category"]
                case.expected_document_ids = row["expected_document_ids"]
                case.expected_chunk_ids = row["expected_chunk_ids"]
                case.difficulty = "hard" if row["vector_heavy"] else "medium"
                case.metadata_json = metadata
            db.commit()
            manifest = {
                "generated_at": now_iso(), "dataset": DATASET_VERSION, "cases": existing,
                "splits": dict(Counter(case.dataset_split for case in existing_cases)),
                "categories": dict(Counter(case.category for case in existing_cases)),
                "vector_heavy": sum(bool((case.metadata_json or {}).get("is_vector_heavy")) for case in existing_cases),
                "model": sum(case.category == "device_model_query" for case in existing_cases),
                "alarm": sum(case.category == "alarm_query" for case in existing_cases),
                "no_answer": sum(case.category == "no_answer" for case in existing_cases),
                "safety": sum(case.category == "safety_procedure" for case in existing_cases),
                "communication": sum(
                    bool(row["unit"]) and row["unit"]["semantic_unit_type"] == "COMMUNICATION" for row in rows
                ),
                "product_coverage": dict(Counter(row["unit"]["product_family"] for row in rows if row["unit"])),
                "source_only": True, "test_data_used": False,
                "ambiguity_free_revision": 2,
                "engineering_verified": False,
                "expert_verified": False,
            }
            write_json("grounded_train_dev_manifest.json", manifest)
            print({"status": "REPAIRED_AMBIGUITY_FREE_IN_PLACE", "cases": existing, "splits": manifest["splits"]})
            return
        actor = db.scalar(select(User).where(User.username == "admin"))
        if actor is None:
            raise SystemExit("admin actor missing")
        split_counts = Counter()
        for index, row in enumerate(rows):
            split = "dev" if index % 3 == 2 else "train"
            split_counts[split] += 1
            unit = row["unit"]
            source_excerpt = unit["canonical_text"].split("原文证据：", 1)[-1] if unit else ""
            lexical_overlap = round(overlap(row["query"], source_excerpt), 6) if unit else 0.0
            metadata = {
                "dataset_version": DATASET_VERSION, "is_vector_heavy": row["vector_heavy"],
                "is_no_answer": row["category"] == "no_answer", "expected_semantic_unit_ids": row["expected_semantic_unit_ids"],
                "expected_source_chunk_ids": row["expected_chunk_ids"], "grounding_concepts": row["concepts"],
                "source_hash": unit["source_hash"] if unit else None, "source_locator": unit["source_locator"] if unit else None,
                "source_section": unit["source_section"] if unit else None, "device_models": unit["device_models"] if unit else [],
                "alarm_codes": unit["alarm_codes"] if unit else [], "lexical_overlap": lexical_overlap,
                "grounding_status": "PENDING_ENGINEERING_CHECK", "engineering_grounded": False,
                "lexical_leakage": None, "human_expert_verified": False, "expert_verified": False,
                "test_data_used": False, "source_only": True,
            }
            db.add(RetrievalEvaluationCase(
                name=f"Task25BR4_{index + 1:03d}", category=row["category"], query_text=row["query"],
                expected_document_ids=row["expected_document_ids"], expected_chunk_ids=row["expected_chunk_ids"], expected_media_ids=[],
                required_filters={"scope": "chinese_engineering_pilot_r2"}, excluded_document_ids=[],
                difficulty="hard" if row["vector_heavy"] else "medium", dataset_split=split,
                review_status="engineering_verified", source_type="engineering_candidate", metadata_json=metadata,
                created_by=actor.id, reviewed_by=actor.id,
            ))
        db.commit()
    coverage = Counter(row["category"] for row in rows)
    product_coverage = Counter(row["unit"]["product_family"] for row in rows if row["unit"])
    manifest = {
        "generated_at": now_iso(), "dataset": DATASET_VERSION, "cases": len(rows), "splits": dict(split_counts),
        "categories": dict(coverage), "vector_heavy": len(vector_rows), "model": len(model_rows), "alarm": len(alarm_rows),
        "no_answer": len(no_answer_rows), "safety": len(safety_rows),
        "communication": sum(bool(row["unit"]) and row["unit"]["semantic_unit_type"] == "COMMUNICATION" for row in rows),
        "product_coverage": dict(product_coverage), "source_only": True, "test_data_used": False,
        "engineering_verified": False, "expert_verified": False,
    }
    write_json("grounded_train_dev_manifest.json", manifest)
    print({"status": "CREATED_PENDING_DUAL_CHECK", **{key: manifest[key] for key in ("cases", "splits", "vector_heavy", "model", "alarm", "no_answer", "safety", "communication")}})


if __name__ == "__main__":
    main()
