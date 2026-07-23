import pytest

from app.models import DiagnosisRecord, KGNode, QARecord
from app.services.record_center_service import RecordCenterService


@pytest.fixture
def record_center_records(db_session, admin_user):
    qa = QARecord(
        question="How to inspect SUN2000 insulation resistance?",
        normalized_query="sun2000 insulation resistance",
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        answer="Inspect DC cables and grounding.",
        references=[],
        retrieved_chunks=[],
        suggested_steps=[],
        safety_notes=["Power off before inspection."],
        related_history=[],
        trace_id="qa-record-center",
        created_by=admin_user.id,
    )
    diagnosis = DiagnosisRecord(
        manufacturer="sungrow",
        product_series="SG",
        device_type="pv_inverter",
        fault_type="communication_interruption",
        fault_description="SG inverter communication interruption",
        possible_causes=["Loose communication cable"],
        inspection_steps=["Inspect communication connector"],
        safety_notes=["Follow lockout procedure"],
        recommended_actions=["Tighten connector"],
        references=[],
        related_history=[],
        media_ids=[],
        trace_id="diagnosis-record-center",
        created_by=admin_user.id,
    )
    graph_node = KGNode(
        node_type="fault",
        canonical_name="low_insulation_resistance",
        display_name="Low insulation resistance",
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        properties_json={},
        confidence=0.9,
        status="active",
        source_type="knowledge_document",
        created_by=admin_user.id,
    )
    db_session.add_all([qa, diagnosis, graph_node])
    db_session.flush()
    return {"qa": qa, "diagnosis": diagnosis, "knowledge_graph_node": graph_node}


def test_record_center_overview_counts_core_records(
    db_session,
    record_center_records,
) -> None:
    overview = RecordCenterService(db_session).overview()
    assert overview["qa_records"] == 1
    assert overview["diagnosis_records"] == 1
    assert overview["knowledge_graph_nodes"] == 1


@pytest.mark.parametrize(
    ("record_type", "expected_manufacturer"),
    [
        ("qa", "huawei"),
        ("diagnosis", "sungrow"),
        ("knowledge_graph_node", "huawei"),
    ],
)
def test_record_center_search_returns_supported_records(
    db_session,
    record_center_records,
    record_type: str,
    expected_manufacturer: str,
) -> None:
    result = RecordCenterService(db_session).search(record_type=record_type)
    assert result["total"] == 1
    assert result["items"][0]["record_type"] == record_type
    assert result["items"][0]["manufacturer"] == expected_manufacturer


@pytest.mark.parametrize(
    "record_type",
    ["qa", "diagnosis", "knowledge_graph_node"],
)
def test_record_center_opens_core_record_details(
    db_session,
    record_center_records,
    record_type: str,
) -> None:
    record = record_center_records[record_type]
    detail = RecordCenterService(db_session).detail(
        record_type=record_type,
        record_id=record.id,
    )
    assert detail["record_type"] == record_type
    assert detail["record_id"] == record.id
    assert detail["record"]["id"] == record.id
