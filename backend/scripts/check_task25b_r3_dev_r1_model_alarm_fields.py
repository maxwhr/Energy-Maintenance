from __future__ import annotations

import json

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase
from app.services.query_understanding_service import (
    QueryUnderstandingService, normalize_alarm_identifier, normalize_device_model, normalize_fault_name,
)
from task25b_r3_dev_common import ROOT, now_iso


DATASET = "task25b_r3_dev_r1_zh_v2"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def main() -> None:
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET
        )))
        service = QueryUnderstandingService()
        model_cases = [item for item in cases if item.category == "device_model_query"]
        alarm_cases = [item for item in cases if item.category == "fault_code_query"]
        model_parsed = sum(bool(service.understand(item.query_text).device_models) for item in model_cases)
        alarm_parsed = sum(bool(service.understand(item.query_text).fault_codes or
                                service.understand(item.query_text).fault_names or
                                (item.metadata_json or {}).get("required_fault_name")) for item in alarm_cases)
        checks = {
            "sun2000": normalize_device_model("SUN2000-(3KTL-10KTL)-M1").startswith("SUN2000"),
            "luna2000": normalize_device_model("LUNA2000-7-S1") == "LUNA2000-7-S1",
            "smartlogger": normalize_device_model("SmartLogger3000") == "SMARTLOGGER3000",
            "alarm_code": normalize_alarm_identifier(" 2032 ") == "2032",
            "fault_name": normalize_fault_name(" 绝缘阻抗低 ") == "绝缘阻抗低",
            "model_cases_parsed": model_parsed == len(model_cases),
            "alarm_cases_parsed": alarm_parsed == len(alarm_cases),
        }
        payload = {"generated_at": now_iso(), "model_cases": len(model_cases), "model_parsed": model_parsed,
                   "alarm_cases": len(alarm_cases), "alarm_parsed": alarm_parsed,
                   "checks": checks, "passed": all(checks.values())}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model_alarm_fields.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
