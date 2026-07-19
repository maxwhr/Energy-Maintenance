import time

from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor


def test_async_completion_order_does_not_change_result_order():
    def work(value):
        time.sleep((4 - value) * 0.002)
        return value

    result = BoundedRetrievalExecutor(max_concurrency=3).execute([1, 2, 3], work)
    assert result.values == [1, 2, 3]
