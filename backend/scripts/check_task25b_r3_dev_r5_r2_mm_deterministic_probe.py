from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService  # noqa: E402
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService  # noqa: E402
from app.services.query_signal_extraction_service import QuerySignalExtractionService  # noqa: E402
from app.services.question_completeness_service import QuestionCompletenessService  # noqa: E402
from app.services.rrf_fusion_service import QueryAwareCandidate  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm" / "deterministic_rerank_probe.json"


def candidate(label: str, content: str, rrf: float, *, exact_model: bool = False, exact_alarm: bool = False) -> QueryAwareCandidate:
    chunk_id = str(uuid4())
    return QueryAwareCandidate(
        candidate_id=label, chunk_id=chunk_id, document_id=str(uuid4()), document_title=f"官方文档 {label}",
        content=content, section_title="故障处理", page_number=3,
        source_channels={"SCOPED_KEYWORD", "RAW_VECTOR"}, source_query_types={"ORIGINAL"},
        raw_scores={"SCOPED_KEYWORD": rrf, "RAW_VECTOR": max(0.0, rrf - 0.01)},
        rrf_score=rrf, final_score=rrf, exact_model_match=exact_model, exact_alarm_match=exact_alarm,
        source_chunk_ids=[chunk_id], source_locator={"page_number": 3, "section": "故障处理"},
        scope_validation_passed=True,
    )


CASES = [
    ("通信掉线是什么原因", "通信掉线的可能原因是线缆松动", "产品参数"),
    ("通信中断如何排查", "通信中断检查与处理步骤", "产品尺寸"),
    ("过温故障的原因", "过温可能由散热异常导致", "版本说明"),
    ("过温故障怎么处理", "过温检查风扇并按步骤处理", "安装尺寸"),
    ("检修有哪些安全要求", "断电验电并采取触电防护", "通信参数"),
    ("操作前置条件", "操作前确认停机和安全条件", "产品参数"),
    ("如何确认恢复", "维修后验证告警消失并确认恢复", "目录"),
    ("风扇异常检查什么", "风扇异常时检查堵塞和供电", "电网参数"),
    ("设备离线原因", "设备离线可能是通信链路断开", "规格表"),
    ("组串异常排查", "检查组串电压和连接状态", "版权页"),
    ("电网过压如何处理", "电网过压检查交流侧电压", "产品概览"),
    ("绝缘阻抗低原因", "绝缘阻抗低可能由组串接地异常导致", "型号列表"),
    ("并网故障步骤", "并网故障按交流侧检查流程处理", "版本记录"),
    ("通信恢复验证", "确认通信在线并验证数据上报", "产品尺寸"),
    ("维护操作顺序", "先断电验电再执行检查步骤", "告警概览"),
    ("部件异常诊断", "检查通信模块和连接部件", "版权声明"),
    ("安全流程冲突", "以断电验电和防护要求为准", "普通说明"),
    ("原因和处理", "列出可能原因并给出对应检查步骤", "产品参数"),
    ("夜间掉线", "夜间通信掉线检查供电和网络条件", "安装尺寸"),
    ("机器没有响应", "设备无响应时检查通信与供电", "版本说明"),
]


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999))], 3)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    service = DeterministicEvidenceRerankService()
    rows = []
    latencies = []
    top1_correct = 0
    boundary_pass = 0
    source_pass = 0
    for index, (query, relevant_text, distractor_text) in enumerate(CASES):
        signals = QuerySignalExtractionService().extract(query)
        understanding = LLMQueryUnderstandingService._deterministic(
            signals, QuestionCompletenessService().assess(signals)
        )
        relevant = candidate(f"relevant-{index}", relevant_text, 0.30)
        distractor = candidate(f"distractor-{index}", distractor_text, 0.31)
        original = [distractor, relevant]
        source_snapshot = {item.candidate_id: (set(item.source_channels), dict(item.source_locator)) for item in original}
        started = time.perf_counter()
        result = service.rerank(original, understanding=understanding)
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        latencies.append(elapsed)
        ids = [item.candidate_id for item in result.candidates]
        expected_id = relevant.candidate_id
        top1_correct += int(ids[0] == expected_id)
        boundary = set(ids) == {distractor.candidate_id, relevant.candidate_id} and len(ids) == 2
        source_unchanged = all(
            (item.source_channels, item.source_locator) == source_snapshot[item.candidate_id]
            for item in result.candidates
        )
        boundary_pass += int(boundary)
        source_pass += int(source_unchanged)
        rows.append({
            "case_id": f"det-{index + 1:02d}",
            "top1_correct": ids[0] == expected_id,
            "boundary_preserved": boundary,
            "sources_preserved": source_unchanged,
            "order_changed": result.diagnostics["order_changed"],
            "latency_ms": elapsed,
        })
    exact_understanding = LLMQueryUnderstandingService._deterministic(
        QuerySignalExtractionService().extract("告警 2031 如何处理"),
        QuestionCompletenessService().assess(QuerySignalExtractionService().extract("告警 2031 如何处理")),
    )
    exact = candidate("exact-alarm", "告警 2031 处理步骤", 0.05, exact_alarm=True)
    broad = candidate("broad", "常见告警处理", 0.9)
    protected = service.rerank(
        [broad, exact], understanding=exact_understanding,
        citation_status={broad.chunk_id: True, exact.chunk_id: True},
    )
    exact_alarm_protected = protected.candidates[0].candidate_id == "exact-alarm"
    no_model_understanding = LLMQueryUnderstandingService._deterministic(
        QuerySignalExtractionService().extract("通信掉线原因"),
        QuestionCompletenessService().assess(QuerySignalExtractionService().extract("通信掉线原因")),
    )
    model_candidate = candidate("model", "SUN2000 通信说明", 0.3, exact_model=True)
    neutral = candidate("neutral", "通信掉线原因", 0.3)
    no_model = service.rerank([model_candidate, neutral], understanding=no_model_understanding)
    no_model_bias = no_model.diagnostics["score_breakdown"]["model"]["exact_model_match"] == 0.0
    passed = all((
        sum(service.weights.values()) == 1.0,
        top1_correct / len(CASES) >= 0.95,
        boundary_pass == len(CASES),
        source_pass == len(CASES),
        exact_alarm_protected,
        no_model_bias,
    ))
    payload = {
        "task": "Task 25B-R3-DEV-R5-R2-MM deterministic rerank probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "cases": len(CASES),
        "candidates": len(CASES) * 2 + 4,
        "weights_version": service.settings.DETERMINISTIC_RERANK_WEIGHTS_VERSION,
        "weights": service.weights,
        "weights_sum": sum(service.weights.values()),
        "top1_accuracy": round(top1_correct / len(CASES), 4),
        "candidate_boundary_preservation": round(boundary_pass / len(CASES), 4),
        "source_preservation": round(source_pass / len(CASES), 4),
        "exact_alarm_protection": exact_alarm_protected,
        "no_model_query_bias": no_model_bias,
        "latency_ms": {"p50": round(statistics.median(latencies), 3), "p95": p95(latencies)},
        "case_results": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)), "status": payload["status"],
        "top1_accuracy": payload["top1_accuracy"], "p95_ms": payload["latency_ms"]["p95"],
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
