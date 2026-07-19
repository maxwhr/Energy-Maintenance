from app.services.rag_performance_trace_service import RagPerformanceTraceService


def test_trace_keeps_hash_and_nullable_metrics_without_query_text():
    query = "SUN2000 告警 2032 怎么处理"
    with RagPerformanceTraceService.trace(trace_id="trace-test", query=query, scope_fingerprint="scope", mode="fast") as trace:
        with RagPerformanceTraceService.stage("request_validation_ms"):
            pass
    row = RagPerformanceTraceService.recent()[-1]
    assert row["query_hash"] and query not in str(row)
    assert row["sql_wait_ms"] is None
    assert trace.stages["request_validation_ms"] >= 0
