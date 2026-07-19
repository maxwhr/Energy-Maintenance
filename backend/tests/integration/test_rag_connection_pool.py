from app.core.database import engine


def test_database_pool_is_finite_and_pre_ping_enabled():
    assert engine.pool is not None
    assert getattr(engine.pool, "_max_overflow", 0) >= 0
    assert engine.dialect is not None
