from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.sop import SOPTemplateRead, normalize_sop_structured_items


def test_sop_structured_items_normalize_strings_without_losing_source_text():
    assert normalize_sop_structured_items(["断电并验电"], default_key="note") == [
        {"note": "断电并验电"}
    ]
    assert normalize_sop_structured_items([{"name": "万用表"}], default_key="name") == [
        {"name": "万用表"}
    ]


def test_sop_template_read_accepts_historical_string_lists():
    now = datetime.now(timezone.utc)
    template = SimpleNamespace(
        id=uuid4(),
        title="兼容性 SOP",
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        fault_type="communication_interruption",
        maintenance_level="level_2",
        steps=[{"step_index": 1, "instruction": "检查通信链路"}],
        safety_requirements=["断电并验电"],
        tools_required=["万用表"],
        materials_required=[],
        compliance_notes=None,
        status="active",
        version=1,
        created_by=None,
        updated_by=None,
        metadata_json={"workflow_id": "mwf_test"},
        created_at=now,
        updated_at=now,
    )

    payload = SOPTemplateRead.model_validate(template)

    assert payload.safety_requirements == [{"note": "断电并验电"}]
    assert payload.tools_required == [{"name": "万用表"}]
