from uuid import uuid4

from app.models import MediaSimilarityFeature
from app.services.multimodal_retrieval_service import MultimodalRetrievalService


def feature(**changes):
    values = dict(media_id=uuid4(), perceptual_hash="0" * 16, difference_hash="f" * 16,
                  ocr_normalized_text="SUN2000 2064", visual_descriptor="descriptor", device_model="SUN2000-100KTL",
                  fault_codes=["2064"], component_tags=["组串"], content_hash="a" * 64, feature_status="active")
    values.update(changes)
    return MediaSimilarityFeature(**values)


def test_media_similarity_exposes_all_scores():
    scores = MultimodalRetrievalService.similarity_breakdown(feature(), feature(), descriptor_vector_score=.9)
    assert scores["perceptual_hash_score"] == 1
    assert scores["device_model_exact"] == 1
    assert scores["fault_code_exact"] == 1
    assert 0 <= scores["final_score"] <= 1
