from types import SimpleNamespace
from uuid import uuid4

from scripts.create_task25g_r1_remediation_plan import evidence_state


def test_historical_evidence_state_capture_is_read_only_and_stable():
    value = SimpleNamespace(
        id=uuid4(),
        node_id=uuid4(),
        edge_id=None,
        source_type="knowledge_document",
        source_id=uuid4(),
        document_id=uuid4(),
        chunk_id=uuid4(),
        created_at="2026-07-15T00:00:00+00:00",
    )
    first = evidence_state(value)
    second = evidence_state(value)
    assert first == second
    assert "production_scope_status" not in first

