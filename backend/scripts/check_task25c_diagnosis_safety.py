from __future__ import annotations

from app.models import MultimodalEvidenceItem
from app.services.multimodal_diagnosis_service import MultimodalDiagnosisService
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution
from app.services.multimodal_evidence_fusion_service import MultimodalEvidenceFusionService
from app.services.multimodal_safety_guard_service import MultimodalSafetyGuardService
from task25c_common import now_iso, write_json


def item(evidence_id: str, text: str, *, confirmed: bool = False) -> MultimodalEvidenceItem:
    return MultimodalEvidenceItem(
        case_id="T25C-SAFETY-PROBE", evidence_id=evidence_id, modality="USER_TEXT", evidence_type="GENERAL_OBSERVATION",
        source_type="USER_INPUT", source_hash=(evidence_id.encode().hex() + "0" * 64)[:64], observed_text=text,
        normalized_text=text, confidence=1.0 if confirmed else .8,
        observation_status="USER_CONFIRMED" if confirmed else "OBSERVED", user_confirmed=confirmed,
        page_or_frame_locator={"source": "test_probe"},
    )


def main() -> int:
    evidence = [item("ev-confirmed", "SUN2000 告警 2001", confirmed=True), item("ev-risk", "设备有烧蚀和冒烟迹象")]
    resolution = MultimodalEntityResolution(
        resolved_device_model="SUN2000-50KTL-M3", resolved_product_family="SUN2000",
        resolved_equipment_category="pv_inverter", resolved_alarm_codes=["2001"], resolution_confidence=1.0,
    )
    fusion = MultimodalEvidenceFusionService().fuse(evidence)
    guard = MultimodalSafetyGuardService()
    safety = guard.evaluate(
        evidence_items=evidence,
        proposed_actions=["带电拆卸并更换熔丝", "停止操作并隔离现场"],
        valid_safety_citations=[], device_state_confirmed_safe=False,
    )
    no_source = MultimodalDiagnosisService().build(
        case_id="T25C-SAFETY-PROBE", resolution=resolution, fusion=fusion, citations=[], safety=safety,
    )
    citation = {
        "citation_id": "citation:probe-chunk", "chunk_id": "00000000-0000-0000-0000-000000000001",
        "document_id": "00000000-0000-0000-0000-000000000002", "document_title": "官方中文手册",
        "section_title": "告警 2001 安全排查", "source_locator": {"page": 1}, "quote": "告警 2001 排查前应完成安全隔离。",
    }
    grounded = MultimodalDiagnosisService().build(
        case_id="T25C-SAFETY-PROBE", resolution=resolution, fusion=fusion, citations=[citation], safety=safety,
    )
    checks = {
        "no_citation_abstains": not no_source.possible_faults and no_source.confidence_status == "INSUFFICIENT_EVIDENCE",
        "grounded_hypothesis_has_citation": bool(grounded.possible_faults and grounded.possible_faults[0].knowledge_citation_ids),
        "unsupported_diagnosis_zero": grounded.unsupported_diagnosis_count == 0,
        "dangerous_action_blocked": "带电拆卸并更换熔丝" in safety.blocked_actions,
        "safe_stop_action_allowed": "停止操作并隔离现场" in safety.allowed_actions,
        "safety_warning_nonempty": bool(safety.safety_warnings),
        "critical_stop_required": safety.stop_required and safety.safety_level == "CRITICAL",
    }
    payload = {
        "generated_at": now_iso(), "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "metrics": {
            "hypotheses": len(grounded.possible_faults), "supported": sum(x.status == "SUPPORTED" for x in grounded.possible_faults),
            "unsupported_diagnoses": grounded.unsupported_diagnosis_count, "unsafe_instructions": 0 if checks["dangerous_action_blocked"] else 1,
            "no_answer_boundary": checks["no_citation_abstains"], "safety_gate": checks["critical_stop_required"],
        },
    }
    write_json("diagnosis_safety.json", payload)
    print(payload["status"])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
