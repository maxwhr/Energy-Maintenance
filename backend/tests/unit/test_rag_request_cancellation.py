from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor


def test_local_failure_does_not_leave_orphaned_result_mutation():
    def work(value):
        if value == "cancelled":
            raise RuntimeError("cancelled")
        return value

    result = BoundedRetrievalExecutor(max_concurrency=2).execute(["ok", "cancelled", "also-ok"], work)
    assert result.values == ["ok", None, "also-ok"]
    assert result.errors == {1: "RuntimeError"}
