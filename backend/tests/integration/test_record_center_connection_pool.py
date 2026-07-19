from concurrent.futures import ThreadPoolExecutor

from app.core.database import SessionLocal, engine
from app.services.record_center_service import RecordCenterService


def _read_once() -> None:
    with SessionLocal() as db:
        RecordCenterService(db).overview()


def test_sessions_return_connections_to_pool() -> None:
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda _index: _read_once(), range(10)))
    assert engine.pool.checkedout() == 0
    assert engine.pool.overflow() <= 10

