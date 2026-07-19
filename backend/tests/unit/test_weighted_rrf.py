from uuid import uuid4

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.hybrid_retrieval_service import HybridRetrievalService, HybridScoredCandidate
from app.services.vector_index_service import VerifiedVectorHit


def _objects(label: str):
    document = KnowledgeDocument(id=uuid4(), title=label, manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="manual", review_status="approved", parse_status="parsed", status="active")
    chunk = KnowledgeChunk(id=uuid4(), document_id=document.id, manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="manual", chunk_index=0, content=label, char_count=len(label), status="active")
    return chunk, document


def test_low_confidence_vector_does_not_demote_strong_keyword():
    keyword_chunk, keyword_doc = _objects("strong keyword")
    vector_chunk, vector_doc = _objects("weak vector")
    result = HybridRetrievalService.merge(
        keyword_candidates=[HybridScoredCandidate(chunk=keyword_chunk, document=keyword_doc, score=10)],
        vector_hits=[VerifiedVectorHit(chunk=vector_chunk, document=vector_doc, score=.60, raw_score=.8, vector_id="v", metadata={})],
        mode="hybrid", keyword_weight=.8, vector_weight=.2, min_score=0, top_k=5,
        vector_similarity_threshold=.72, rrf_k=40,
    )
    assert result[0].chunk.id == keyword_chunk.id
    assert all(item.chunk.id != vector_chunk.id for item in result)

