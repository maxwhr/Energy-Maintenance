import threading
import time

from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor


def test_many_query_variants_never_exceed_configured_workers():
    active = peak = 0
    lock = threading.Lock()

    def work(value):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.005)
        with lock:
            active -= 1
        return value

    result = BoundedRetrievalExecutor(max_concurrency=3).execute(list(range(20)), work)
    assert result.values == list(range(20))
    assert peak == 3
