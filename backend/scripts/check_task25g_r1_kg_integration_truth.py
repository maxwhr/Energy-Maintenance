from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from task25g_r1_common import BACKEND, now_iso, read_json, write_json


def _fact_evidence_pairs(context: dict[str, Any]) -> list[tuple[str, list[str]]]:
    pairs: list[tuple[str, list[str]]] = []
    for key in ("matched_nodes", "kg_nodes"):
        for item in context.get(key) or []:
            if isinstance(item, dict) and item.get("id"):
                pairs.append((f"node:{item['id']}", [str(value) for value in item.get("evidence_ids") or []]))
    for item in context.get("kg_edges") or []:
        if isinstance(item, dict) and item.get("id"):
            pairs.append((f"edge:{item['id']}", [str(value) for value in item.get("evidence_ids") or []]))
    for group in (
        "related_faults",
        "related_alarms",
        "related_causes",
        "inspection_items",
        "recommended_actions",
        "safety_risks",
        "related_sop",
        "tools",
        "parts",
    ):
        for item in context.get(group) or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            pairs.append((f"group:{group}:{item['id']}", [str(value) for value in item.get("evidence_ids") or []]))
            if item.get("via_edge_id"):
                pairs.append(
                    (
                        f"via_edge:{item['via_edge_id']}",
                        [str(value) for value in item.get("via_evidence_ids") or []],
                    )
                )
    return pairs


def _static_boundaries() -> dict[str, Any]:
    from app.services.diagnosis_service import DiagnosisService
    from app.services.workflow_correction_service import WorkflowCorrectionService

    diagnosis_source = inspect.getsource(DiagnosisService._resolve_kg_context)
    correction_source = inspect.getsource(WorkflowCorrectionService)
    workflow_paths = sorted((BACKEND / "app" / "services").glob("workflow_*_service.py"))
    workflow_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in workflow_paths)
    graph_write_markers = (
        "KGNode(",
        "KGEdge(",
        "KGEvidenceLink(",
        "create_node(",
        "create_edge(",
        "create_evidence(",
        "approve_candidate(",
    )
    return {
        "diagnosis_calls_production_business_context": (
            "KnowledgeGraphService" in diagnosis_source and ".business_context(" in diagnosis_source
        ),
        "diagnosis_returns_kg_evidence": "kg_evidence" in (BACKEND / "app" / "services" / "diagnosis_service.py").read_text(
            encoding="utf-8", errors="replace"
        ),
        "workflow_automatic_graph_writes": sum(workflow_text.count(marker) for marker in graph_write_markers),
        "correction_creates_review_model_only": (
            "ModelOutputCorrection(" in correction_source
            and ("review_status=\"draft\"" in correction_source or "review_status=\"pending_review\"" in correction_source)
            and "automatic_knowledge_update\": False" in correction_source
            and "expert_verified\": False" in correction_source
            and all(marker not in correction_source for marker in graph_write_markers)
        ),
        "correction_requires_completed_task": "requires a completed task" in correction_source,
        "knowledge_curator_explicit_review": _knowledge_curator_review_boundary(),
    }


def _knowledge_curator_review_boundary() -> bool:
    candidate_path = BACKEND / "app" / "services" / "kg_candidate_service.py"
    extraction_path = BACKEND / "app" / "services" / "kg_extraction_service.py"
    candidate = candidate_path.read_text(encoding="utf-8", errors="replace") if candidate_path.is_file() else ""
    extraction = extraction_path.read_text(encoding="utf-8", errors="replace") if extraction_path.is_file() else ""
    return (
        "Only experts and admins" in candidate
        and "status=\"pending\"" in extraction
        and "approved" in candidate
        and "reviewed_by" in candidate
    )


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGNode
    from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService
    from app.services.knowledge_graph_service import KnowledgeGraphService

    baseline = read_json("leakage_baseline.json", {})
    leaked_ids = {str(value) for value in baseline.get("evidence_ids") or []}
    total_pairs = 0
    grounded_pairs = 0
    unsupported_facts: set[str] = set()
    leaked_returned: set[str] = set()
    invalid_locators: set[str] = set()
    context_count = 0
    evidence_returned_count = 0
    with SessionLocal() as session:
        nodes = list(session.scalars(select(KGNode).where(KGNode.status == "active").order_by(KGNode.id.asc())))
        scope_service = KnowledgeGraphProductionScopeService(session)
        production_scope = scope_service.evaluate(node_ids=[node.id for node in nodes])
        production_nodes = [node for node in nodes if node.id in production_scope.eligible_node_ids]
        service = KnowledgeGraphService(session)
        for node in production_nodes:
            context = service.business_context(
                manufacturer=node.manufacturer,
                product_series=node.product_series,
                question=node.canonical_name,
                limit=80,
            )
            context_count += 1
            evidence = {
                str(item.get("id")): item
                for item in context.get("evidence") or []
                if isinstance(item, dict) and item.get("id")
            }
            evidence_returned_count += len(evidence)
            leaked_returned.update(set(evidence) & leaked_ids)
            for evidence_id, item in evidence.items():
                locator = item.get("source_locator") or {}
                if (
                    item.get("scope_status") != "CURRENT_VALID"
                    or not locator.get("document_id")
                    or not locator.get("chunk_id")
                    or locator.get("chunk_index") is None
                ):
                    invalid_locators.add(evidence_id)
            for fact_id, fact_evidence_ids in _fact_evidence_pairs(context):
                total_pairs += 1
                if fact_evidence_ids and all(value in evidence for value in fact_evidence_ids):
                    grounded_pairs += 1
                else:
                    unsupported_facts.add(fact_id)

        empty_context = service.business_context(question="task25g-r1-no-such-fact-7f296f", limit=20)
        safe_degradation = (
            not empty_context.get("matched_nodes")
            and not empty_context.get("kg_nodes")
            and not empty_context.get("kg_edges")
            and not empty_context.get("evidence")
        )

    static = _static_boundaries()
    citation_coverage = grounded_pairs / total_pairs if total_pairs else 1.0
    failures = []
    if citation_coverage != 1.0:
        failures.append("citation_preservation")
    if invalid_locators:
        failures.append("source_locator_coverage")
    if unsupported_facts:
        failures.append("unsupported_graph_facts")
    if leaked_returned:
        failures.append("archived_evidence_returned")
    if not static["diagnosis_calls_production_business_context"]:
        failures.append("diagnosis_grounding")
    if static["workflow_automatic_graph_writes"]:
        failures.append("workflow_automatic_graph_writes")
    if not static["correction_creates_review_model_only"]:
        failures.append("correction_candidate_boundary")
    if not static["knowledge_curator_explicit_review"]:
        failures.append("knowledge_curator_explicit_review")
    if not safe_degradation:
        failures.append("safe_degradation")
    payload = {
        "version": "task25g_r1_kg_integration_truth_v1",
        "generated_at": now_iso(),
        "status": "PASS" if not failures else "FAIL",
        "runtime_context_count": context_count,
        "production_node_probe_count": len(production_nodes),
        "returned_evidence_observations": evidence_returned_count,
        "citation_preservation": round(citation_coverage, 6),
        "source_locator_coverage": 1.0 if not invalid_locators else 0.0,
        "production_context_empty": not bool(production_nodes),
        "unsupported_graph_fact_returned": len(unsupported_facts),
        "archived_baseline_evidence_returned": len(leaked_returned),
        "diagnosis_grounding": static["diagnosis_calls_production_business_context"],
        "diagnosis_returns_kg_evidence": static["diagnosis_returns_kg_evidence"],
        "workflow_automatic_graph_writes": static["workflow_automatic_graph_writes"],
        "correction_candidate_boundary": static["correction_creates_review_model_only"],
        "correction_requires_completed_task": static["correction_requires_completed_task"],
        "knowledge_curator_explicit_review": static["knowledge_curator_explicit_review"],
        "safe_degradation": "PASS" if safe_degradation else "FAIL",
        "invalid_locator_evidence_ids": sorted(invalid_locators),
        "unsupported_fact_ids": sorted(unsupported_facts),
        "leaked_evidence_ids_returned": sorted(leaked_returned),
        "failures": failures,
    }
    write_json("kg_integration_truth.json", payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "citation_preservation": payload["citation_preservation"],
                "unsupported_graph_fact_returned": payload["unsupported_graph_fact_returned"],
                "archived_evidence_returned": payload["archived_baseline_evidence_returned"],
                "workflow_graph_writes": payload["workflow_automatic_graph_writes"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
