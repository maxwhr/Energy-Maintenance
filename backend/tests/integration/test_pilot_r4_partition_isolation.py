import pytest

from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService


def test_r4_service_rejects_r2_r3_and_default_partitions() -> None:
    for partition in ("pilot_r2", "pilot_r3_semantic", "default"):
        with pytest.raises(ValueError, match="pilot_r4_grounded"):
            SemanticUnitRetrievalService(None, allow_real_api=False, collection_name="collection", namespace=partition)
