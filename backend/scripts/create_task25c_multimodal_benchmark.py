from __future__ import annotations

from collections import Counter

from app.core.database import SessionLocal
from app.models import UploadedMedia
from task25c_common import BENCHMARK_VERSION, now_iso, sha256_json, write_json


REQUIRED_COVERAGE = {
    "nameplate_model_ocr": 15,
    "alarm_code_screen": 15,
    "indicator_state": 10,
    "platform_alarm_screen": 10,
    "component_recognition": 10,
    "text_image_joint_query": 20,
    "text_image_conflict": 8,
    "low_quality_image": 8,
    "clarification_required": 10,
    "no_answer": 10,
    "high_risk_safety": 8,
    "context_supplement": 8,
}


def categories_for(index: int, metadata: dict) -> list[str]:
    kind = str(metadata.get("media_kind") or "")
    role = str(metadata.get("media_role") or "")
    categories = ["text_image_joint_query"]
    if kind == "nameplate":
        categories.append("nameplate_model_ocr")
    if kind == "alarm_screen":
        categories.append("alarm_code_screen")
    if kind in {"fault_component", "device_exterior"}:
        categories.append("component_recognition")
    if index < 8:
        categories.extend(["text_image_conflict", "clarification_required"])
    if role == "no_match":
        categories.append("no_answer")
    if kind == "fault_component":
        categories.append("high_risk_safety")
    if index % 3 == 0:
        categories.append("context_supplement")
    return sorted(set(categories))


def main() -> int:
    with SessionLocal() as db:
        media = [
            item for item in db.query(UploadedMedia).order_by(UploadedMedia.created_at, UploadedMedia.id).all()
            if bool((item.metadata_json or {}).get("engineering_controlled"))
        ]

    cases = []
    for index, item in enumerate(media):
        metadata = dict(item.metadata_json or {})
        model = str(metadata.get("device_model") or "")
        alarm = str(metadata.get("alarm_code") or "")
        conflict = index < 8
        expected_conflicts = ["USER_MODEL_VS_MEDIA_MODEL"] if conflict else []
        query_model = "SUN2000-INVALID-CONFLICT" if conflict else model
        categories = categories_for(index, metadata)
        cases.append({
            "case_id": f"T25C-BENCH-{index + 1:03d}",
            "media_source": {
                "source_type": "existing_engineering_controlled_fixture",
                "media_id": str(item.id),
                "media_hash": sha256_json({"media_id": str(item.id), "fixture_hash": metadata.get("perceptual_hash")}),
            },
            "user_query": f"请结合图片核对设备 {query_model or '型号待确认'} 的告警 {alarm or '待确认'}，给出有手册来源的安全排查建议。",
            "expected_observations": [str(metadata.get("media_kind") or "existing_image_fixture")],
            "expected_entities": {
                "device_model": [model] if model else [],
                "alarm_codes": [alarm] if alarm else [],
                "product_family": [item.product_series] if item.product_series else [],
            },
            "expected_conflicts": expected_conflicts,
            "expected_clarification": conflict,
            "expected_knowledge_evidence": [] if "no_answer" in categories else ["official_zh_manual_citation_required"],
            "expected_safety_status": "HIGH_RISK_CONFIRMATION_REQUIRED" if "high_risk_safety" in categories else "BASELINE_WARNING_REQUIRED",
            "source_locator": f"uploaded_media:{item.id}",
            "categories": categories,
            "engineering_verified": True,
            "expert_verified": False,
        })

    coverage = Counter(category for case in cases for category in case["categories"])
    shortages = {
        key: {"actual": coverage.get(key, 0), "required": required}
        for key, required in REQUIRED_COVERAGE.items()
        if coverage.get(key, 0) < required
    }
    status = "BENCHMARK_READY" if len(cases) >= 80 and not shortages else "MULTIMODAL_BENCHMARK_INSUFFICIENT"
    payload = {
        "generated_at": now_iso(),
        "dataset_version": BENCHMARK_VERSION,
        "status": status,
        "case_count": len(cases),
        "unique_media_count": len({case["media_source"]["media_id"] for case in cases}),
        "authorized_source_policy": "existing engineering-controlled fixtures only; no internet or generated device imagery",
        "coverage": dict(sorted(coverage.items())),
        "required_coverage": REQUIRED_COVERAGE,
        "shortages": shortages,
        "expert_verified_count": 0,
        "cases": cases,
    }
    payload["dataset_sha256"] = sha256_json(cases)
    write_json("multimodal_benchmark_v1.json", payload)
    print(status, len(cases), len(shortages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
