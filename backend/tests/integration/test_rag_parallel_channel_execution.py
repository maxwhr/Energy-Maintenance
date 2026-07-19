import time

from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor


def test_independent_channels_execute_in_parallel_with_bound():
    started = time.perf_counter()
    result = BoundedRetrievalExecutor(max_concurrency=3).execute([1, 2, 3], lambda value: (time.sleep(0.03), value)[1])
    elapsed = time.perf_counter() - started
    assert result.values == [1, 2, 3]
    assert elapsed < 0.08
