from app.services.task25g_r2_grounding_service import (
    ALLOWED_GROUNDING_OPERATIONS,
    Task25GR2GroundingService,
)


def test_grounding_plan_is_deterministic_and_contains_only_allowed_operations():
    manifest = {
        "manifest_sha256": "manifest",
        "gate": {"passed": False},
        "facts": [],
    }
    facts = [{"fact_id": "node:1", "identity_hash": "identity"}]
    first = Task25GR2GroundingService.build_plan(
        manifest=manifest, all_facts=facts, historical_evidence_ids=["evidence-1"]
    )
    second = Task25GR2GroundingService.build_plan(
        manifest=manifest, all_facts=facts, historical_evidence_ids=["evidence-1"]
    )
    assert first["plan_sha256"] == second["plan_sha256"]
    assert {item["operation"] for item in first["operations"]} <= ALLOWED_GROUNDING_OPERATIONS
    assert first["status"] == "TASK25G_R2_GROUNDING_PLAN_REJECTED"

