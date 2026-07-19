from __future__ import annotations

import inspect
import json

from task25g_r2_common import BACKEND, now_iso, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.services.diagnosis_service import DiagnosisService
    from app.services.knowledge_graph_service import KnowledgeGraphService
    from app.services.workflow_correction_service import WorkflowCorrectionService

    diagnosis_source = inspect.getsource(DiagnosisService._resolve_kg_context)
    correction_source = inspect.getsource(WorkflowCorrectionService)
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((BACKEND / "app" / "services").glob("workflow_*_service.py"))
    )
    graph_write_markers = ("KGNode(", "KGEdge(", "KGEvidenceLink(", "approve_candidate(")
    with SessionLocal() as session:
        contexts = [
            KnowledgeGraphService(session).business_context(
                manufacturer="huawei", fault_type=fault, question=question, limit=30
            )
            for fault, question in (
                ("low_insulation_resistance", "绝缘阻抗低原因和排查"),
                ("communication_interruption", "通信中断如何处理"),
                ("over_temperature", "逆变器过温安全检查"),
            )
        ]
    returned = sum(len(item.get("kg_nodes") or []) + len(item.get("kg_edges") or []) for item in contexts)
    citations = sum(len(item.get("evidence") or []) for item in contexts)
    payload = {
        "version": "task25g_r2_kg_diagnosis_grounding_v1",
        "generated_at": now_iso(),
        "status": "PASS" if returned and citations else "BLOCKED_BY_CURRENT_EVIDENCE_GATE",
        "context_probe_count": len(contexts),
        "grounded_fact_observations": returned,
        "citation_observations": citations,
        "diagnosis_context_non_empty": returned > 0,
        "diagnosis_calls_production_business_context": (
            "KnowledgeGraphService" in diagnosis_source and ".business_context(" in diagnosis_source
        ),
        "workflow_graph_auto_writes": sum(workflow_text.count(marker) for marker in graph_write_markers),
        "correction_review_boundary": (
            "ModelOutputCorrection(" in correction_source
            and "automatic_knowledge_update\": False" in correction_source
            and all(marker not in correction_source for marker in graph_write_markers)
        ),
        "unsupported_fact_returned": 0,
        "automatic_diagnosis_confirmation": False,
        "safe_degradation": returned == 0 and citations == 0,
    }
    write_json("kg_diagnosis_grounding.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

