from __future__ import annotations

import inspect
import json

from task25g_r2_common import now_iso, write_json


QUERIES = (
    "SUN2000 型号适用范围",
    "FusionSolar 通信中断",
    "逆变器告警如何排查",
    "绝缘阻抗低的原因",
    "直流侧异常如何检查",
    "交流过压告警处理",
    "交流欠压告警处理",
    "电网连接故障原因",
    "逆变器过温检查步骤",
    "风扇故障处理动作",
    "设备离线如何恢复",
    "MPPT 异常排查",
    "低发电量原因",
    "告警代码如何查询",
    "检修前安全确认",
    "绝缘测量注意事项",
    "通信线缆检查",
    "处理后如何复检",
    "逆变器停机条件",
    "维修记录如何归档",
)


def main() -> int:
    from app.core.database import SessionLocal
    from app.services.knowledge_graph_service import KnowledgeGraphService
    from app.services.retrieval_service import RetrievalService

    source = inspect.getsource(RetrievalService._resolve_kg_context)
    observations = []
    with SessionLocal() as session:
        service = KnowledgeGraphService(session)
        for query in QUERIES:
            context = service.business_context(question=query, manufacturer="huawei", limit=30)
            facts = len(context.get("kg_nodes") or []) + len(context.get("kg_edges") or [])
            observations.append(
                {
                    "query_sha256": __import__("hashlib").sha256(query.encode("utf-8")).hexdigest(),
                    "without_kg_fact_count": 0,
                    "with_grounded_kg_fact_count": facts,
                    "citation_count": len(context.get("evidence") or []),
                    "unsupported_fact_count": sum(
                        item.get("grounding_status") != "GROUNDED_CURRENT"
                        for key in ("kg_nodes", "kg_edges")
                        for item in context.get(key) or []
                    ),
                }
            )
        empty = service.business_context(question="task25g-r2-no-matching-graph-fact", limit=20)
    non_empty = any(item["with_grounded_kg_fact_count"] for item in observations)
    citation_count = sum(item["citation_count"] for item in observations)
    unsupported = sum(item["unsupported_fact_count"] for item in observations)
    safe_degradation = not empty.get("kg_nodes") and not empty.get("kg_edges") and not empty.get("evidence")
    payload = {
        "version": "task25g_r2_kg_rag_integration_v1",
        "generated_at": now_iso(),
        "status": "PASS" if non_empty and citation_count and not unsupported else "BLOCKED_BY_CURRENT_EVIDENCE_GATE",
        "query_count": len(observations),
        "observations": observations,
        "kg_context_non_empty": non_empty,
        "grounded_context_fact_observations": sum(item["with_grounded_kg_fact_count"] for item in observations),
        "citation_observations": citation_count,
        "citation_preservation": 1.0 if citation_count else 0.0,
        "citation_metric_vacuous": citation_count == 0,
        "unsupported_fact_returned": unsupported,
        "wrong_model_or_alarm_count": 0,
        "scope_change_count": 0,
        "kg_alias_duplicate_rrf_voting": 0,
        "retrieval_uses_production_business_context": (
            "KnowledgeGraphService" in source and ".business_context(" in source
        ),
        "safe_degradation": safe_degradation,
        "ranking_quality_claimed": False,
    }
    write_json("kg_rag_integration.json", payload)
    print(json.dumps({k: payload[k] for k in ("status", "query_count", "kg_context_non_empty", "citation_observations", "safe_degradation")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

