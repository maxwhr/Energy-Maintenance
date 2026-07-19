from uuid import uuid4

from app.models import KGEvidenceLink, KnowledgeChunk, KnowledgeDocument
from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService


def test_archived_evidence_is_excluded_without_deleting_the_link():
    document_id = uuid4()
    chunk_id = uuid4()
    document = KnowledgeDocument(
        id=document_id,
        title="Historical record",
        manufacturer="huawei",
        device_type="pv_inverter",
        document_type="maintenance_record",
        parse_status="parsed",
        review_status="approved",
        status="archived",
        metadata_json={"normalized_language": "en"},
    )
    chunk = KnowledgeChunk(
        id=chunk_id,
        document_id=document_id,
        manufacturer="huawei",
        device_type="pv_inverter",
        document_type="maintenance_record",
        chunk_index=0,
        content="historical observation",
        char_count=22,
        status="active",
    )
    evidence = KGEvidenceLink(
        id=uuid4(),
        node_id=uuid4(),
        source_type="knowledge_document",
        document_id=document_id,
        chunk_id=chunk_id,
    )
    reasons = KnowledgeGraphProductionScopeService.evidence_reasons(evidence, document, chunk)
    assert "lifecycle_archived" in reasons
    assert evidence.id is not None

