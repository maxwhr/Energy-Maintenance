from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KGEdge, KGEvidenceLink, KGNode, KnowledgeChunk, KnowledgeDocument, User


DEMO_SOURCE = "final_demo_kg_seed"


NODE_SEEDS = [
    ("manufacturer", "huawei", "华为", "huawei", "SUN2000"),
    ("manufacturer", "sungrow", "阳光电源", "sungrow", "SG"),
    ("product_series", "SUN2000", "SUN2000", "huawei", "SUN2000"),
    ("product_series", "FusionSolar", "FusionSolar", "huawei", "FusionSolar"),
    ("product_series", "SG", "SG 系列", "sungrow", "SG"),
    ("device_model", "SUN2000-50KTL", "SUN2000-50KTL", "huawei", "SUN2000"),
    ("device_model", "SG125HX", "SG125HX", "sungrow", "SG"),
    ("fault", "low_insulation_resistance", "绝缘阻抗低", "huawei", "SUN2000"),
    ("fault", "communication_interruption", "通信中断", "huawei", "SUN2000"),
    ("fault", "over_temperature", "过温", "sungrow", "SG"),
    ("fault", "mppt_abnormal", "MPPT 异常", "sungrow", "SG"),
    ("alarm", "ALM-2001", "ALM-2001 绝缘告警", "huawei", "SUN2000"),
    ("alarm", "A-503", "A-503 通信告警", "sungrow", "SG"),
    ("component", "dc_side", "直流侧", "huawei", "SUN2000"),
    ("component", "ac_side", "交流侧", "sungrow", "SG"),
    ("component", "fan", "风扇", "sungrow", "SG"),
    ("component", "communication_module", "通信模块", "huawei", "SUN2000"),
    ("cause", "moisture", "受潮", "huawei", "SUN2000"),
    ("cause", "grounding_abnormal", "接地异常", "huawei", "SUN2000"),
    ("cause", "fan_blocked", "风扇堵转", "sungrow", "SG"),
    ("symptom", "alarm", "告警", "huawei", "SUN2000"),
    ("symptom", "offline", "离线", "huawei", "SUN2000"),
    ("action", "measure", "测量", "huawei", "SUN2000"),
    ("action", "power_off", "断电", "huawei", "SUN2000"),
    ("action", "clean", "清理", "sungrow", "SG"),
    ("tool", "multimeter", "万用表", "huawei", "SUN2000"),
    ("tool", "insulation_tester", "绝缘电阻测试仪", "huawei", "SUN2000"),
    ("tool", "thermal_imager", "热成像仪", "sungrow", "SG"),
    ("safety_risk", "high_voltage", "高压风险", "huawei", "SUN2000"),
    ("safety_risk", "ppe", "个人防护", "sungrow", "SG"),
]

EDGE_SEEDS = [
    ("SUN2000", "huawei", "BELONGS_TO", "属于"),
    ("FusionSolar", "huawei", "BELONGS_TO", "属于"),
    ("SG", "sungrow", "BELONGS_TO", "属于"),
    ("SUN2000-50KTL", "SUN2000", "BELONGS_TO", "属于"),
    ("SG125HX", "SG", "BELONGS_TO", "属于"),
    ("low_insulation_resistance", "ALM-2001", "HAS_ALARM", "关联告警"),
    ("communication_interruption", "A-503", "HAS_ALARM", "关联告警"),
    ("low_insulation_resistance", "alarm", "HAS_SYMPTOM", "表现为"),
    ("communication_interruption", "offline", "HAS_SYMPTOM", "表现为"),
    ("over_temperature", "alarm", "HAS_SYMPTOM", "表现为"),
    ("mppt_abnormal", "alarm", "HAS_SYMPTOM", "表现为"),
    ("low_insulation_resistance", "moisture", "CAUSED_BY", "可能原因"),
    ("low_insulation_resistance", "grounding_abnormal", "CAUSED_BY", "可能原因"),
    ("over_temperature", "fan_blocked", "CAUSED_BY", "可能原因"),
    ("low_insulation_resistance", "dc_side", "CHECK_BY", "排查部件"),
    ("communication_interruption", "communication_module", "CHECK_BY", "排查部件"),
    ("over_temperature", "fan", "CHECK_BY", "排查部件"),
    ("mppt_abnormal", "dc_side", "CHECK_BY", "排查部件"),
    ("low_insulation_resistance", "measure", "RESOLVED_BY", "处理措施"),
    ("communication_interruption", "power_off", "RESOLVED_BY", "处理措施"),
    ("over_temperature", "clean", "RESOLVED_BY", "处理措施"),
    ("low_insulation_resistance", "insulation_tester", "USES_TOOL", "使用工具"),
    ("communication_interruption", "multimeter", "USES_TOOL", "使用工具"),
    ("over_temperature", "thermal_imager", "USES_TOOL", "使用工具"),
    ("low_insulation_resistance", "high_voltage", "HAS_SAFETY_RISK", "安全风险"),
    ("communication_interruption", "high_voltage", "HAS_SAFETY_RISK", "安全风险"),
    ("over_temperature", "ppe", "HAS_SAFETY_RISK", "安全风险"),
    ("mppt_abnormal", "multimeter", "USES_TOOL", "使用工具"),
    ("SUN2000", "low_insulation_resistance", "HAS_FAULT", "关联故障"),
    ("SUN2000", "communication_interruption", "HAS_FAULT", "关联故障"),
    ("SG", "over_temperature", "HAS_FAULT", "关联故障"),
    ("SG", "mppt_abnormal", "HAS_FAULT", "关联故障"),
]


def ensure_final_demo_data_if_needed() -> None:
    db = SessionLocal()
    try:
        document = db.execute(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.review_status == "approved",
                KnowledgeDocument.status == "active",
            )
            .order_by(KnowledgeDocument.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
    finally:
        db.close()
    if document:
        return
    import seed_final_demo_data

    seed_final_demo_data.main()


def first_document_and_chunk(db) -> tuple[KnowledgeDocument, KnowledgeChunk | None]:
    document = db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.status == "active",
        )
        .order_by(KnowledgeDocument.created_at.asc())
        .limit(1)
    ).scalar_one()
    chunk = db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document.id, KnowledgeChunk.status == "active")
        .order_by(KnowledgeChunk.chunk_index.asc())
        .limit(1)
    ).scalar_one_or_none()
    return document, chunk


def get_admin(db) -> User | None:
    return db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()


def ensure_node(db, *, document: KnowledgeDocument, admin: User | None, values: tuple[str, str, str, str, str]) -> KGNode:
    node_type, canonical_name, display_name, manufacturer, product_series = values
    node = db.execute(
        select(KGNode).where(
            KGNode.node_type == node_type,
            KGNode.canonical_name == canonical_name,
            KGNode.manufacturer == manufacturer,
            KGNode.product_series == product_series,
            KGNode.device_type == "pv_inverter",
        )
        .limit(1)
    ).scalar_one_or_none()
    if not node:
        node = KGNode(
            node_type=node_type,
            canonical_name=canonical_name,
            display_name=display_name,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type="pv_inverter",
            properties_json={"seed_source": DEMO_SOURCE},
            confidence=0.86,
            status="active",
            source_type=DEMO_SOURCE,
            source_id=document.id,
            created_by=admin.id if admin else None,
        )
        db.add(node)
        db.flush()
    else:
        node.display_name = display_name
        node.status = "active"
        node.properties_json = {**(node.properties_json or {}), "seed_source": DEMO_SOURCE}
    return node


def ensure_edge(db, *, nodes: dict[str, KGNode], document: KnowledgeDocument, admin: User | None, values: tuple[str, str, str, str]) -> KGEdge:
    source_name, target_name, relation_type, display_relation = values
    source_node = nodes[source_name]
    target_node = nodes[target_name]
    edge = db.execute(
        select(KGEdge).where(
            KGEdge.source_node_id == source_node.id,
            KGEdge.target_node_id == target_node.id,
            KGEdge.relation_type == relation_type,
        )
        .limit(1)
    ).scalar_one_or_none()
    if not edge:
        edge = KGEdge(
            source_node_id=source_node.id,
            target_node_id=target_node.id,
            relation_type=relation_type,
            display_relation=display_relation,
            properties_json={"seed_source": DEMO_SOURCE},
            confidence=0.82,
            evidence_count=0,
            status="active",
            source_type=DEMO_SOURCE,
            source_id=document.id,
            created_by=admin.id if admin else None,
        )
        db.add(edge)
        db.flush()
    else:
        edge.display_relation = display_relation
        edge.status = "active"
        edge.properties_json = {**(edge.properties_json or {}), "seed_source": DEMO_SOURCE}
    return edge


def evidence_exists(db, *, node_id: UUID | None = None, edge_id: UUID | None = None) -> bool:
    filters = [KGEvidenceLink.source_type == DEMO_SOURCE]
    if node_id:
        filters.append(KGEvidenceLink.node_id == node_id)
    if edge_id:
        filters.append(KGEvidenceLink.edge_id == edge_id)
    return db.execute(select(KGEvidenceLink).where(*filters).limit(1)).scalar_one_or_none() is not None


def add_evidence(db, *, document: KnowledgeDocument, chunk: KnowledgeChunk | None, node: KGNode | None = None, edge: KGEdge | None = None) -> None:
    if evidence_exists(db, node_id=node.id if node else None, edge_id=edge.id if edge else None):
        return
    db.add(
        KGEvidenceLink(
            node_id=node.id if node else None,
            edge_id=edge.id if edge else None,
            source_type=DEMO_SOURCE,
            source_id=document.id,
            document_id=document.id,
            chunk_id=chunk.id if chunk else None,
            evidence_text=(chunk.content[:500] if chunk else document.summary) or "PV inverter maintenance demo evidence",
            confidence=0.82,
        )
    )
    if edge:
        edge.evidence_count = (edge.evidence_count or 0) + 1


def main() -> int:
    ensure_final_demo_data_if_needed()
    db = SessionLocal()
    try:
        document, chunk = first_document_and_chunk(db)
        admin = get_admin(db)
        nodes: dict[str, KGNode] = {}
        for seed in NODE_SEEDS:
            node = ensure_node(db, document=document, admin=admin, values=seed)
            nodes[seed[1]] = node
            add_evidence(db, document=document, chunk=chunk, node=node)
        edge_count = 0
        for seed in EDGE_SEEDS:
            edge = ensure_edge(db, nodes=nodes, document=document, admin=admin, values=seed)
            add_evidence(db, document=document, chunk=chunk, edge=edge)
            edge_count += 1
        db.commit()
        print(
            {
                "status": "ok",
                "nodes": len(NODE_SEEDS),
                "edges": edge_count,
                "source_document_id": str(document.id),
                "source_chunk_id": str(chunk.id) if chunk else None,
            }
        )
        return 0
    except Exception as exc:
        db.rollback()
        print({"status": "failed", "error": str(exc)})
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
