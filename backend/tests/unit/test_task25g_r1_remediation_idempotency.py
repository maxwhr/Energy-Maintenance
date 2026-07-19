from types import SimpleNamespace

from scripts.apply_task25g_r1_kg_grounding_remediation import _logical_candidate
from task25g_r1_common import sha256_value


def test_logical_candidate_hash_ignores_generated_database_identity():
    desired = {
        "target_type": "node",
        "target_id": "00000000-0000-0000-0000-000000000001",
        "candidate_type": "grounding_remediation",
        "status": "pending",
        "production_grounding_status": "UNSUPPORTED_CURRENT_SOURCE",
        "source_evidence_ids": ["evidence-a", "evidence-b"],
        "expert_verified": False,
    }
    candidate = SimpleNamespace(
        candidate_type="grounding_remediation",
        status="pending",
        payload_json={**desired, "source_evidence_ids": ["evidence-a", "evidence-b"], "remediation_plan_id": "x"},
    )
    assert sha256_value(_logical_candidate(candidate)) == sha256_value(desired)
