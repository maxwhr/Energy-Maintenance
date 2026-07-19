from uuid import uuid4

from app.models import KGNode
from app.services.kg_alias_resolution_policy_service import KGAliasResolutionPolicyService


def node(*, manufacturer: str, canonical_name: str) -> KGNode:
    return KGNode(
        id=uuid4(),
        node_type="alarm",
        canonical_name=canonical_name,
        manufacturer=manufacturer,
        device_type="pv_inverter",
        properties_json={},
        status="active",
    )


def test_context_dependent_alias_requires_disambiguating_context():
    huawei = node(manufacturer="huawei", canonical_name="alarm-a")
    sungrow = node(manufacturer="sungrow", canonical_name="alarm-b")
    unresolved = KGAliasResolutionPolicyService.resolve_candidates([huawei, sungrow])
    assert unresolved.resolution_status == "CONTEXT_DEPENDENT"
    assert unresolved.clarification_required
    resolved = KGAliasResolutionPolicyService.resolve_candidates(
        [huawei, sungrow], context={"manufacturer": "huawei"}
    )
    assert resolved.resolved_node_id == huawei.id
    assert not resolved.clarification_required


def test_incompatible_alias_never_auto_resolves():
    first = node(manufacturer="huawei", canonical_name="alarm-a")
    second = node(manufacturer="huawei", canonical_name="alarm-b")
    result = KGAliasResolutionPolicyService.resolve_candidates([first, second])
    assert result.resolution_status == "INCOMPATIBLE"
    assert result.resolved_node_id is None

