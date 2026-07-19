import threading
import time

from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor


def test_bounded_executor_preserves_input_order_and_local_failures():
    active = maximum = 0
    lock = threading.Lock()

    def work(value):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            time.sleep(0.01)
            if value == 2:
                raise ValueError("local")
            return value * 10
        finally:
            with lock:
                active -= 1

    result = BoundedRetrievalExecutor(max_concurrency=2).execute([3, 1, 2, 4], work)
    assert result.values[:2] == [30, 10]
    assert result.values[3] == 40
    assert result.errors == {2: "ValueError"}
    assert maximum <= 2
