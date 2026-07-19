from app.services.grounded_benchmark_validation import overlap


def test_paraphrased_query_stays_below_vector_heavy_overlap_threshold() -> None:
    query = "现场涉及Echonet功能时链路异常，应核对哪些通信条件？"
    source = "设置Echonet时需要检查通信参数、网络连接状态并确认配置生效。"
    assert overlap(query, source) < 0.18
