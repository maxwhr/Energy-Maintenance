from types import SimpleNamespace
from uuid import uuid4

from app.services.retrieval_pilot_service import RetrievalPilotService


def test_pilot_session_only_routes_scoped_user_or_prefixed_privileged_query():
    user_id = uuid4()
    service = RetrievalPilotService.__new__(RetrievalPilotService)
    service.settings = SimpleNamespace(DASHVECTOR_PHYSICAL_COLLECTION="base")
    service.repository = SimpleNamespace(active_sessions=lambda: [SimpleNamespace(
        id=uuid4(), collection_name="pilot", metadata_json={
            "scope_user_ids": [str(user_id)], "query_prefix": "Task25BR2_",
            "retrieval_strategy": "adaptive", "audit_trace_id": "trace",
        },
    )])
    scoped = service.route_for(SimpleNamespace(id=user_id, role="expert"), "普通查询")
    normal = service.route_for(SimpleNamespace(id=uuid4(), role="viewer"), "普通查询")
    assert scoped.active is True and scoped.collection == "pilot"
    assert normal.active is False and normal.collection == "base"
