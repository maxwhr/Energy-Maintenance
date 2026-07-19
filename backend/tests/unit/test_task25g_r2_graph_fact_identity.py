from uuid import UUID

from app.models import KGNode
from app.services.knowledge_graph_fact_identity_service import KnowledgeGraphFactIdentityService


def test_node_fact_identity_is_content_stable_and_normalized():
    node = KGNode(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        node_type="device_model",
        canonical_name="ＳＵＮ 2000",
        display_name="SUN2000",
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        properties_json={},
        status="active",
    )
    first = KnowledgeGraphFactIdentityService.node_identity(node)
    second = KnowledgeGraphFactIdentityService.node_identity(node)
    assert first["normalized_key"] == "sun2000"
    assert first["stable_fact_key"] == second["stable_fact_key"]
    assert first["identity_hash"] == second["identity_hash"]
    assert first["fact_kind"] == "NODE"

