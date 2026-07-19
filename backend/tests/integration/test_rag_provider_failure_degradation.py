from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor


def test_one_provider_failure_preserves_other_channel_results():
    def channel(name):
        if name == "semantic":
            raise TimeoutError("provider timeout")
        return [name]

    result = BoundedRetrievalExecutor(max_concurrency=3).execute(["keyword", "semantic", "raw"], channel)
    assert result.values == [["keyword"], None, ["raw"]]
    assert result.errors == {1: "TimeoutError"}
