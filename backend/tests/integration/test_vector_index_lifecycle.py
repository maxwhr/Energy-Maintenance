from app.core.database import SessionLocal
from app.services.vector_index_service import VectorIndexService


def test_vector_index_lifecycle_report_is_postgresql_backed():
    with SessionLocal() as db:
        result = VectorIndexService(db, allow_real_api=False).lifecycle_report()
    assert "approved_active_chunks" in result
    assert result["external_collection_scan_performed"] is False
