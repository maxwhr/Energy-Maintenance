from __future__ import annotations

import hashlib
from collections import Counter
from uuid import UUID

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, User
from app.services.grounded_benchmark_validation import grounded_query, topic_hint
from task25b_r3_dev_r4_common import OUT, now_iso, read_json, write_json


DATASET = "task25b_r3_dev_r4_zh_v4"


def require_canary() -> dict:
    result = read_json(OUT / "canary_iteration_2.json") or read_json(OUT / "canary_iteration_1.json")
    if not result.get("passed"):
        raise SystemExit("formal v4 creation blocked: Grounded Canary has not passed")
    return result


def pick(pool: list[dict], count: int, used: set[str], predicate=lambda unit: True) -> list[dict]:
    chosen = []
    for unit in pool:
        if unit["semantic_unit_id"] in used or not predicate(unit):
            continue
        chosen.append(unit); used.add(unit["semantic_unit_id"])
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise SystemExit(f"formal v4 source coverage incomplete: requested {count}, found {len(chosen)}")
    return chosen


def main() -> None:
    canary = require_canary()
    units = read_json(OUT / "semantic_units.json").get("units") or []
    canary_case_ids = {UUID(value) for value in (canary.get("case_ids") or [])}
    with SessionLocal() as db:
        canary_hashes = {
            hashlib.sha256(case.query_text.encode()).hexdigest()
            for case in db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.id.in_(canary_case_ids)))
        }
    units = sorted(units, key=lambda unit: hashlib.sha256(unit["semantic_unit_id"].encode()).hexdigest())
    used: set[str] = set()
    test_vector = []
    for predicate, count in (
        (lambda unit: unit.get("product_family") == "SUN2000" and unit.get("safety_terms"), 8),
        (lambda unit: unit.get("product_family") == "SUN2000", 4),
        (lambda unit: unit.get("product_family") == "LUNA2000", 6),
        (lambda unit: unit.get("product_family") == "SmartLogger" and unit.get("semantic_unit_type") == "COMMUNICATION", 6),
        (lambda unit: unit.get("product_family") == "FusionSolar", 1),
    ):
        test_vector.extend(pick(units, count, used, predicate))
    test_model = pick(units, 10, used, lambda unit: bool(unit.get("device_models")))
    test_alarm = pick(units, 10, used, lambda unit: bool(unit.get("alarm_codes")))
    remaining = [unit for unit in units if unit["semantic_unit_id"] not in used and topic_hint(unit)]
    train_positive = remaining[:100]
    dev_positive = remaining[100:150]
    if len(train_positive) != 100 or len(dev_positive) != 50:
        raise SystemExit("insufficient source-grounded units for formal v4 train/dev")

    no_answer = [
        "风力发电机齿轮箱油温异常怎么处理？", "柴油发电机喷油泵压力是多少？", "矿用提升机钢丝绳如何验收？",
        "电动汽车制动液更换周期是多少？", "水轮机导叶间隙标准是什么？", "燃气轮机点火失败如何处理？",
        "锅炉给水泵汽蚀如何排查？", "铁路信号机灯丝报警如何复位？", "船舶主机滑油压力低怎么办？",
        "空压机冷却水流量标准是多少？", "煤矿皮带机跑偏如何校正？", "电梯曳引轮磨损限值是多少？",
        "数控机床主轴振动如何诊断？", "航空发动机叶片裂纹如何处置？", "化工泵机械密封泄漏怎么办？",
        "起重机钢丝绳报废标准是什么？", "轨道车辆车轮踏面磨耗限值？", "蒸汽轮机轴瓦温度高如何处理？",
        "液压挖掘机主泵压力如何调整？", "冷库压缩机回液如何判断？", "船用雷达磁控管如何更换？",
        "炼钢转炉倾动故障如何排查？", "无人机电机失速如何处置？", "内燃机气门间隙如何调整？",
        "食品灌装机无菌阀如何维护？", "纺织机锭子振动标准是什么？", "港口岸桥制动器如何测试？",
        "高铁受电弓碳滑板磨耗限值？", "注塑机锁模力不足如何检查？", "农业拖拉机离合器打滑怎么办？",
        "锅炉水位计冲洗步骤是什么？", "风机叶片结冰如何除冰？", "矿井通风机喘振如何处理？",
        "汽车变速箱换挡冲击如何诊断？", "船舶舵机液压油如何更换？", "机床导轨几何精度如何检测？",
        "压缩空气露点标准是多少？", "水泵叶轮汽蚀如何修复？", "燃烧器火焰检测器如何校准？",
        "铁路道岔转换阻力如何测量？", "叉车门架链条如何润滑？", "锅炉安全阀如何定压？",
        "发动机涡轮增压器异响怎么办？", "制氧机分子筛如何再生？", "塔吊力矩限制器如何标定？",
    ]

    rows: list[dict] = []
    def add_positive(unit: dict, split: str, category: str, query: str, vector_heavy: bool) -> None:
        rows.append({"unit": unit, "split": split, "category": category, "query": query, "vector_heavy": vector_heavy})
    for unit in train_positive:
        add_positive(unit, "train", "semantic_vector_heavy", grounded_query(unit)[0], True)
    for unit in dev_positive:
        add_positive(unit, "dev", "semantic_vector_heavy", grounded_query(unit)[0], True)
    for unit in test_vector:
        add_positive(unit, "test_v4", "semantic_vector_heavy", grounded_query(unit)[0], True)
    for unit in test_model:
        add_positive(unit, "test_v4", "device_model_query", f"{unit['device_models'][0]} 涉及的检修现象或操作要点是什么？", False)
    for unit in test_alarm:
        add_positive(unit, "test_v4", "alarm_query", f"告警代码 {unit['alarm_codes'][0]} 对应的现象与处理动作是什么？", False)
    for index, query in enumerate(no_answer):
        rows.append({"unit": None, "split": "train" if index < 20 else "dev" if index < 30 else "test_v4",
                     "category": "no_answer", "query": query, "vector_heavy": False})
    if Counter(row["split"] for row in rows) != {"train": 120, "dev": 60, "test_v4": 60}:
        raise SystemExit(f"formal v4 split mismatch: {Counter(row['split'] for row in rows)}")
    if any(hashlib.sha256(str(row.get("query")).encode()).hexdigest() in canary_hashes for row in rows):
        raise SystemExit("formal v4 overlaps Canary")

    with SessionLocal() as db:
        existing = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET
        )) or 0)
        if existing:
            if existing != 240:
                raise SystemExit(f"formal v4 already exists with unexpected {existing} cases")
            print({"status": "PRESERVED_EXISTING", "dataset": DATASET, "cases": existing})
            return
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
        if admin is None:
            raise SystemExit("admin actor required")
        for index, row in enumerate(rows):
            unit = row["unit"]
            db.add(RetrievalEvaluationCase(
                name=f"Task25BR4V4_{index + 1:03d}", category=row["category"], query_text=row["query"],
                expected_document_ids=[unit["document_id"]] if unit else [],
                expected_chunk_ids=unit["source_chunk_ids"] if unit else [], expected_media_ids=[],
                required_filters={"scope": "chinese_engineering_pilot_r2"}, excluded_document_ids=[],
                difficulty="hard" if row["vector_heavy"] else "medium", dataset_split=row["split"],
                review_status="engineering_verified", source_type="engineering_candidate",
                metadata_json={
                    "dataset_version": DATASET, "expected_semantic_unit_ids": [unit["semantic_unit_id"]] if unit else [],
                    "expected_source_chunk_ids": unit["source_chunk_ids"] if unit else [],
                    "source_locator": unit["source_locator"] if unit else None, "source_hash": unit["source_hash"] if unit else None,
                    "is_vector_heavy": row["vector_heavy"], "is_no_answer": unit is None,
                    "engineering_grounded": True, "expert_verified": False, "human_expert_verified": False,
                    "test_v4_frozen": False, "canary_overlap": False, "source_only": True,
                }, created_by=admin.id, reviewed_by=admin.id,
            ))
        db.commit()
    manifest = {
        "generated_at": now_iso(), "dataset": DATASET, "cases": 240,
        "splits": {"train": 120, "dev": 60, "test_v4": 60},
        "test_v4": {"vector_heavy": 25, "model": 10, "alarm": 10, "no_answer": 15,
                    "safety": sum(bool(unit.get("safety_terms")) for unit in test_vector),
                    "communication": sum(unit.get("semantic_unit_type") == "COMMUNICATION" for unit in test_vector),
                    "storage": sum(unit.get("product_family") == "LUNA2000" for unit in test_vector),
                    "inverter": sum(unit.get("product_family") == "SUN2000" for unit in test_vector),
                    "smartlogger": sum(unit.get("product_family") == "SmartLogger" for unit in test_vector)},
        "canary_overlap": 0, "test_data_used_for_tuning": False, "expert_verified": False,
    }
    write_json("dataset_v4_manifest.json", manifest)
    print({"status": "CREATED", **manifest})


if __name__ == "__main__":
    main()
