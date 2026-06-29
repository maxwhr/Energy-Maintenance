from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal
from app.models import SOPTemplate
from app.services.sop_rule_engine import SOPRuleEngine


DEMO_TEMPLATES = [
    {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000",
        "fault_type": "low_insulation",
        "maintenance_level": "level_2",
    },
    {
        "manufacturer": "huawei",
        "product_series": "FusionSolar",
        "model": "FusionSolar",
        "fault_type": "communication_fault",
        "maintenance_level": "level_2",
    },
    {
        "manufacturer": "sungrow",
        "product_series": "SG",
        "model": "SG",
        "fault_type": "overtemperature",
        "maintenance_level": "level_2",
    },
    {
        "manufacturer": "sungrow",
        "product_series": "SG",
        "model": "SG",
        "fault_type": "mppt_low_power",
        "maintenance_level": "level_2",
    },
]


def main() -> None:
    engine = SOPRuleEngine()
    db = SessionLocal()
    created = 0
    updated = 0
    try:
        for item in DEMO_TEMPLATES:
            rule_result = engine.generate(
                manufacturer=item["manufacturer"],
                product_series=item["product_series"],
                model=item["model"],
                fault_type=item["fault_type"],
                alarm_code=None,
                maintenance_level=item["maintenance_level"],
            )
            existing = (
                db.query(SOPTemplate)
                .filter(
                    SOPTemplate.manufacturer == item["manufacturer"],
                    SOPTemplate.product_series == item["product_series"],
                    SOPTemplate.device_type == "pv_inverter",
                    SOPTemplate.fault_type == rule_result.fault_type,
                    SOPTemplate.maintenance_level == item["maintenance_level"],
                    SOPTemplate.title == rule_result.title,
                )
                .one_or_none()
            )
            if existing:
                existing.steps = rule_result.steps
                existing.safety_requirements = rule_result.safety_requirements
                existing.tools_required = rule_result.tools_required
                existing.materials_required = rule_result.materials_required
                existing.compliance_notes = rule_result.compliance_notes
                existing.status = "active"
                existing.version = max(existing.version or 1, 1)
                existing.metadata_json = {"seed": "demo_sop", "engine": rule_result.metadata.get("engine_name")}
                updated += 1
            else:
                db.add(
                    SOPTemplate(
                        title=rule_result.title,
                        manufacturer=item["manufacturer"],
                        product_series=item["product_series"],
                        device_type="pv_inverter",
                        fault_type=rule_result.fault_type,
                        maintenance_level=item["maintenance_level"],
                        steps=rule_result.steps,
                        safety_requirements=rule_result.safety_requirements,
                        tools_required=rule_result.tools_required,
                        materials_required=rule_result.materials_required,
                        compliance_notes=rule_result.compliance_notes,
                        status="active",
                        version=1,
                        metadata_json={"seed": "demo_sop", "engine": rule_result.metadata.get("engine_name")},
                    )
                )
                created += 1
        db.commit()
        print(f"demo_sop_seed_result created={created} updated={updated}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
