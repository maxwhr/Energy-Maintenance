from concurrent.futures import ThreadPoolExecutor

from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from scripts.task25e_common import sha256_value


def _overview_hash() -> str:
    with SessionLocal() as db:
        return sha256_value(RecordCenterService(db).overview())


def test_five_concurrent_readers_receive_identical_response() -> None:
    # Record Center is a live view: later acceptance suites legitimately add
    # business records.  Freeze the expected value at the start of this test
    # instead of coupling concurrency safety to an old database snapshot.
    expected = _overview_hash()
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _index: _overview_hash(), range(10)))
    assert results == [expected] * 10
