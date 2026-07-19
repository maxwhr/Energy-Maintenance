from app.models import RetrievalOfficialRunLock


def test_official_run_lock_has_database_unique_scope():
    names = {constraint.name for constraint in RetrievalOfficialRunLock.__table__.constraints}
    assert "uq_retrieval_official_run_lock_scope" in names
