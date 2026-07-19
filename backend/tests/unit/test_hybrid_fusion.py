from uuid import uuid4

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.hybrid_retrieval_service import HybridRetrievalService, HybridScoredCandidate
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.vector_index_service import VerifiedVectorHit


def objects():
    document = KnowledgeDocument(id=uuid4(), title="SUN2000 2064 手册", manufacturer="huawei", product_series="SUN2000",
                                 device_type="pv_inverter", document_type="manual", review_status="approved", parse_status="parsed", status="active")
    chunk = KnowledgeChunk(id=uuid4(), document_id=document.id, manufacturer="huawei", product_series="SUN2000", device_type="pv_inverter",
                           document_type="manual", chunk_index=0, content="SUN2000-100KTL 告警2064绝缘排查", char_count=25, status="active")
    return chunk, document


def test_hybrid_fusion_returns_explainable_rrf_and_exact_boosts():
    chunk, document = objects()
    keyword = HybridScoredCandidate(chunk=chunk, document=document, score=10)
    vector = VerifiedVectorHit(chunk=chunk, document=document, score=.9, raw_score=.8, vector_id="v", metadata={"vector_backend": "dashvector"})
    result = HybridRetrievalService.merge(keyword_candidates=[keyword], vector_hits=[vector], mode="hybrid_rerank",
        keyword_weight=.35, vector_weight=.65, min_score=0, top_k=5,
        query_analysis=QueryUnderstandingService().understand("SUN2000-100KTL 2064"))
    assert result[0].rrf_score > 0
    assert result[0].exact_model_boost > 0
    assert result[0].exact_fault_code_boost > 0
    assert result[0].final_score is not None
