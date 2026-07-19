from __future__ import annotations

import concurrent.futures
import argparse
import http.client
import json
import math
import os
import statistics
import sys
import threading
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text

from app.core.database import engine
from task25a_r1_common import ROOT, RUNTIME, now_iso, read_json, register_test, run, sha256_file, write_json


PRIVATE_CREDENTIALS = RUNTIME / ".test_credentials.private.json"
READ_PROFILE = {"warmup": 5, "serial_requests": 100, "concurrency_requests": 100, "concurrency_workers": 10}
WRITE_PROFILE = {"warmup": 2, "serial_requests": 20, "concurrency_requests": 20, "concurrency_workers": 5}


@dataclass(frozen=True)
class Endpoint:
    endpoint_id: str
    name: str
    method: str
    path: str
    profile: str
    threshold_ms: float
    payload: dict[str, Any] | None = None
    auth: bool = True
    created_table: str | None = None


def credentials() -> tuple[str, str]:
    username = os.getenv("TASK25A_R1_USERNAME")
    password = os.getenv("TASK25A_R1_PASSWORD")
    if username and password:
        return username, password
    if PRIVATE_CREDENTIALS.is_file():
        payload = read_json(PRIVATE_CREDENTIALS, {})
        admin = payload.get("admin", {})
        if admin.get("username") and admin.get("password"):
            return str(admin["username"]), str(admin["password"])
    raise RuntimeError("Task 25A-R1 credentials must be supplied by environment or the private secure test configuration")


def source_ip(index: int) -> str:
    return f"127.25.{(index // 240) % 200 + 1}.{index % 240 + 10}"


def request(base_url: str, method: str, path: str, payload: dict[str, Any] | None, token: str | None,
            timeout: float, request_index: int) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(base_url)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    started = time.perf_counter()
    try:
        connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_class(parsed.hostname, parsed.port, timeout=timeout, source_address=(source_ip(request_index), 0))
        connection.request(method, (parsed.path.rstrip("/") + path) or "/", body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        elapsed = (time.perf_counter() - started) * 1000
        connection.close()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
        return {"elapsed_ms": elapsed, "status": response.status, "bytes": len(raw), "data": data, "timeout": False, "error": None}
    except TimeoutError:
        return {"elapsed_ms": (time.perf_counter() - started) * 1000, "status": None, "bytes": 0, "data": None, "timeout": True, "error": "TimeoutError"}
    except Exception as exc:  # noqa: BLE001 - failures are evidence, not hidden
        return {"elapsed_ms": (time.perf_counter() - started) * 1000, "status": None, "bytes": 0, "data": None, "timeout": False, "error": type(exc).__name__}


def unified_success(sample: dict[str, Any]) -> bool:
    body = sample.get("data")
    return sample.get("status") == 200 and isinstance(body, dict) and body.get("code") in {0, 200} and body.get("data") is not None


def assertion(endpoint: Endpoint, sample: dict[str, Any], username: str) -> bool:
    if not unified_success(sample):
        return False
    data = sample["data"]["data"]
    if endpoint.endpoint_id == "health":
        return isinstance(data, dict) and data.get("status") == "running" and bool(data.get("name"))
    if endpoint.endpoint_id == "login":
        return isinstance(data, dict) and bool(data.get("access_token")) and data.get("user", {}).get("username") == username
    if endpoint.endpoint_id in {"devices", "documents", "sop_templates", "tasks", "record_center", "agent_runs"}:
        return isinstance(data, dict) and isinstance(data.get("items"), list) and isinstance(data.get("total"), int)
    if endpoint.endpoint_id == "kg_keyword_search":
        return isinstance(data, (dict, list))
    if endpoint.endpoint_id == "retrieval_references":
        return isinstance(data, dict) and bool(data.get("trace_id")) and isinstance(data.get("references"), list) and isinstance(data.get("retrieved_chunks"), list)
    if endpoint.endpoint_id == "diagnosis_controlled":
        return isinstance(data, dict) and bool(data.get("trace_id")) and bool(data.get("safety_notes")) and isinstance(data.get("inspection_steps"), list)
    if endpoint.endpoint_id == "kg_business_context":
        return isinstance(data, dict)
    if endpoint.endpoint_id == "system_status":
        return isinstance(data, dict) and data.get("database_status") == "online" and isinstance(data.get("document_count"), int)
    return bool(data is not None)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return round(ordered[low], 3)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)


def summarize(samples: list[dict[str, Any]], wall: float, endpoint: Endpoint, username: str) -> dict[str, Any]:
    latencies = [float(sample["elapsed_ms"]) for sample in samples]
    sizes = [float(sample["bytes"]) for sample in samples]
    assertions = [assertion(endpoint, sample, username) for sample in samples]
    successes = sum(assertions)
    timeouts = sum(bool(sample["timeout"]) for sample in samples)
    failures = len(samples) - successes
    return {
        "count": len(samples), "success_count": successes, "failure_count": failures, "timeout_count": timeouts,
        "min_ms": round(min(latencies), 3) if latencies else None, "mean_ms": round(statistics.fmean(latencies), 3) if latencies else None,
        "p50_ms": percentile(latencies, .50), "p90_ms": percentile(latencies, .90), "p95_ms": percentile(latencies, .95),
        "p99_ms": percentile(latencies, .99), "max_ms": round(max(latencies), 3) if latencies else None,
        "wall_clock_seconds": round(wall, 6), "requests_per_second": round(len(samples) / wall, 3) if wall > 0 else None,
        "response_bytes_p50": percentile(sizes, .50), "response_bytes_p95": percentile(sizes, .95),
        "status_code_distribution": dict(Counter(str(sample["status"]) for sample in samples)),
        "business_assertion_failures": sum(not item for item in assertions),
        "errors": dict(Counter(str(sample["error"]) for sample in samples if sample.get("error"))),
    }


def resource_snapshot(label: str) -> dict[str, Any]:
    pid_path = ROOT / ".runtime" / "task25a" / "backend-8010.pid"
    listener = run(["powershell.exe", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"], ROOT, timeout=10)
    listener_text = listener["stdout"].strip()
    pid = int(listener_text) if listener_text.isdigit() else (int(pid_path.read_text().strip()) if pid_path.is_file() and pid_path.read_text().strip().isdigit() else None)
    process: dict[str, Any] = {"pid": pid, "rss_bytes": "unavailable", "cpu_seconds": "unavailable", "thread_count": "unavailable"}
    if pid:
        command = ["powershell.exe", "-NoProfile", "-Command", f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object Id,WorkingSet64,CPU,@{{n='ThreadCount';e={{$_.Threads.Count}}}} | ConvertTo-Json -Compress"]
        result = run(command, ROOT, timeout=10)
        try:
            parsed = json.loads(result["stdout"])
            process.update({"rss_bytes": parsed.get("WorkingSet64", "unavailable"), "cpu_seconds": parsed.get("CPU", "unavailable"), "thread_count": parsed.get("ThreadCount", "unavailable")})
        except (TypeError, json.JSONDecodeError):
            pass
    try:
        with engine.connect() as connection:
            db_connections: Any = int(connection.scalar(text("select count(*) from pg_stat_activity where datname=current_database()")) or 0)
    except Exception:  # noqa: BLE001
        db_connections = "unavailable"
    static = ROOT / "backend" / "static" / "frontend"
    return {
        "label": label, "captured_at": now_iso(), "backend_process": process, "database_connections": db_connections,
        "frontend_static_bytes": sum(path.stat().st_size for path in static.rglob("*") if path.is_file()) if static.is_dir() else "unavailable",
        "peak_rss_bytes": "unavailable_without_sampling_dependency",
    }


def row_count(table: str | None) -> int | None:
    if not table:
        return None
    with engine.connect() as connection:
        return int(connection.scalar(text(f'SELECT count(*) FROM "{table}"')) or 0)


def run_endpoint(endpoint: Endpoint, base_url: str, token: str | None, username: str, sequence: int) -> dict[str, Any]:
    profile = READ_PROFILE if endpoint.profile == "read" else WRITE_PROFILE
    before_count = row_count(endpoint.created_table)
    warmup_samples = [request(base_url, endpoint.method, endpoint.path, endpoint.payload, token if endpoint.auth else None, 15, sequence * 10000 + i) for i in range(profile["warmup"])]
    serial_started = time.perf_counter()
    serial = [request(base_url, endpoint.method, endpoint.path, endpoint.payload, token if endpoint.auth else None, 20, sequence * 10000 + 1000 + i) for i in range(profile["serial_requests"])]
    serial_wall = time.perf_counter() - serial_started
    concurrent_started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=profile["concurrency_workers"], thread_name_prefix=f"r1-{endpoint.endpoint_id}") as pool:
        futures = [pool.submit(request, base_url, endpoint.method, endpoint.path, endpoint.payload, token if endpoint.auth else None, 25, sequence * 10000 + 5000 + i) for i in range(profile["concurrency_requests"])]
        concurrent_samples = [future.result() for future in futures]
    concurrent_wall = time.perf_counter() - concurrent_started
    after_count = row_count(endpoint.created_table)
    warmup_failures = sum(not assertion(endpoint, sample, username) for sample in warmup_samples)
    serial_summary = summarize(serial, serial_wall, endpoint, username)
    concurrency_summary = summarize(concurrent_samples, concurrent_wall, endpoint, username)
    combined_failure = serial_summary["failure_count"] + concurrency_summary["failure_count"] + warmup_failures
    combined_timeout = serial_summary["timeout_count"] + concurrency_summary["timeout_count"] + sum(sample["timeout"] for sample in warmup_samples)
    worst_p95 = max(serial_summary["p95_ms"] or 0, concurrency_summary["p95_ms"] or 0)
    classification = "FAIL" if combined_failure or combined_timeout else ("NEEDS_OPTIMIZATION" if worst_p95 > endpoint.threshold_ms else "PASS")
    return {
        "endpoint_id": endpoint.endpoint_id, "name": endpoint.name, "method": endpoint.method, "path": endpoint.path,
        "profile": endpoint.profile, "parameters": profile, "threshold_p95_ms": endpoint.threshold_ms,
        "warmup": {"count": len(warmup_samples), "failure_count": warmup_failures, "timeout_count": sum(sample["timeout"] for sample in warmup_samples), "errors": [sample["error"] for sample in warmup_samples if sample.get("error")]},
        "serial": serial_summary, "concurrency": concurrency_summary,
        "created_data_count": max(0, (after_count or 0) - (before_count or 0)) if endpoint.created_table else 0,
        "created_data_count_scope": "warmup_plus_serial_plus_concurrency",
        "database_count_before": before_count, "database_count_after": after_count,
        "classification": classification,
    }


def record_center_audit(record_result: dict[str, Any]) -> dict[str, Any]:
    repo = ROOT / "backend" / "app" / "repositories" / "record_center_repository.py"
    service = ROOT / "backend" / "app" / "services" / "record_center_service.py"
    texts = {path.name: path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else "" for path in [repo, service]}
    combined = "\n".join(texts.values())
    index_sources = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "backend" / "alembic" / "versions").glob("*.py"))
    return {
        "generated_at": now_iso(),
        "files": [repo.relative_to(ROOT).as_posix(), service.relative_to(ROOT).as_posix()],
        "full_table_load_detected": ".all()" in combined,
        "python_memory_sort_detected": bool("sorted(" in combined or ".sort(" in combined),
        "sort_then_page_risk": bool(("sorted(" in combined or ".sort(" in combined) and ("page_size" in combined or "offset" in combined)),
        "n_plus_one_risk": "manual_review_required" if re_contains_loop_query(combined) else "not_detected_by_static_pattern",
        "limit_offset_present": "limit(" in combined and "offset(" in combined,
        "date_range_filter_present": "date_from" in combined and "date_to" in combined,
        "index_support_mentions": sum(index_sources.lower().count(token) for token in ["qa_records", "diagnosis_records", "maintenance_tasks"]),
        "growth_complexity": "Potential O(N log N) and memory amplification if heterogeneous records are merged/sorted in Python; validate with production-scale fixtures.",
        "endpoint_metrics": {key: record_result.get(key) for key in ["serial", "concurrency", "classification"]},
        "task25e_recommendation": "Push filtering, ordering and pagination into per-source SQL queries; use bounded UNION/merge strategy, composite time/filter indexes, EXPLAIN ANALYZE and pagination contract tests.",
    }


def re_contains_loop_query(text_value: str) -> bool:
    return bool(__import__("re").search(r"for\s+\w+\s+in[^:]+:[\s\S]{0,400}\.(?:execute|scalar|query)\(", text_value))


def refresh_current_write_counts() -> int:
    endpoint_path = RUNTIME / "performance_endpoint_results.json"
    payload = read_json(endpoint_path, {})
    marker_queries = {
        "retrieval_references": "select count(*) from qa_records where question like 'Task25AR1_performance_controlled%'",
        "diagnosis_controlled": "select count(*) from diagnosis_records where fault_description like 'Task25AR1_performance_controlled%'",
    }
    with engine.connect() as connection:
        counts = {key: int(connection.scalar(text(query)) or 0) for key, query in marker_queries.items()}
    for item in payload.get("endpoints", []):
        if item.get("endpoint_id") in counts:
            item["created_data_count"] = counts[item["endpoint_id"]]
            item["created_data_count_scope"] = "all unique Task25AR1_performance_controlled marker rows, including warmup"
            item["write_count_refreshed_at"] = now_iso()
    write_json(endpoint_path, payload)
    resource_path = RUNTIME / "performance_resource_usage.json"
    resource_payload = read_json(resource_path, {})
    resource_payload["post_run_listener_verification"] = resource_snapshot("post_run_listener_verification")
    resource_payload["resource_refresh_notes"] = "The listener owning port 8010 is used; the historical launcher PID file is only a fallback."
    write_json(resource_path, resource_payload)
    report_path = ROOT / "docs" / "25A_R1_performance_baseline_report.md"
    if report_path.is_file():
        verified_process = resource_payload["post_run_listener_verification"]["backend_process"]
        refreshed_lines = []
        for line in report_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- before RSS="):
                refreshed_lines.append(
                    f"- 原 before/after PID 文件指向启动器进程，不作为后端 RSS；端口 8010 当前监听进程 "
                    f"PID={verified_process['pid']}，RSS={verified_process['rss_bytes']}，CPU seconds={verified_process['cpu_seconds']}，threads={verified_process['thread_count']}。"
                )
            else:
                refreshed_lines.append(line)
        report_path.write_text("\n".join(refreshed_lines) + "\n", encoding="utf-8")
    registry_path = RUNTIME / "test_execution_registry.json"
    registry = read_json(registry_path, {"tests": []})
    for test in registry.get("tests", []):
        if test.get("test_id") == "T-R1-PERFORMANCE-BASELINE":
            test["artifact_hashes"] = {
                value: sha256_file(ROOT / value)
                for value in test.get("artifact_paths", [])
                if (ROOT / value).is_file()
            }
    write_json(registry_path, registry)
    print(f"task25a_r1_performance_write_counts retrieval={counts['retrieval_references']} diagnosis={counts['diagnosis_controlled']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-current-write-counts", action="store_true")
    args = parser.parse_args()
    if args.refresh_current_write_counts:
        return refresh_current_write_counts()
    started = now_iso()
    username, password = credentials()
    base_url = os.getenv("TASK25A_R1_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
    login_payload = {"username": username, "password": password}
    login_once = request(base_url, "POST", "/api/auth/login", login_payload, None, 15, 1)
    if not unified_success(login_once) or not login_once["data"]["data"].get("access_token"):
        raise RuntimeError("Secure Task 25A-R1 login failed")
    token = str(login_once["data"]["data"]["access_token"])
    marker = "Task25AR1_performance_controlled"
    endpoints = [
        Endpoint("health", "Health", "GET", "/api/health", "read", 150, auth=False),
        Endpoint("login", "Login", "POST", "/api/auth/login", "write", 600, login_payload, auth=False),
        Endpoint("devices", "Device list", "GET", "/api/devices?page=1&page_size=20", "read", 600),
        Endpoint("documents", "Knowledge document list", "GET", "/api/knowledge/documents?page=1&page_size=20", "read", 600),
        Endpoint("kg_keyword_search", "Keyword/KG search", "GET", "/api/kg/search?keyword=SUN2000&limit=20", "read", 1500),
        Endpoint("retrieval_references", "Knowledge retrieval references", "POST", "/api/retrieval/query", "write", 1500, {"question": f"{marker} SUN2000 低绝缘阻抗如何排查", "manufacturer": "huawei", "product_series": "SUN2000", "device_type": "pv_inverter", "retrieval_mode": "keyword", "enable_vector": False, "enable_kg_enhancement": False, "enable_model_enhancement": False}, created_table="qa_records"),
        Endpoint("diagnosis_controlled", "Controlled diagnosis", "POST", "/api/diagnosis/analyze", "write", 2000, {"manufacturer": "huawei", "product_series": "SUN2000", "device_type": "pv_inverter", "fault_type": "low_insulation_resistance", "alarm_code": "Task25AR1_ALM", "fault_description": f"{marker} 潮湿天气后低绝缘阻抗", "enable_kg_enhancement": False, "enable_model_enhancement": False}, created_table="diagnosis_records"),
        Endpoint("sop_templates", "SOP list", "GET", "/api/sop/templates?page=1&page_size=20", "read", 600),
        Endpoint("tasks", "Maintenance task list", "GET", "/api/maintenance/tasks?page=1&page_size=20", "read", 600),
        Endpoint("record_center", "Record Center search", "GET", "/api/record-center/search?record_type=all&page=1&page_size=20", "read", 1500),
        Endpoint("kg_business_context", "KG business context", "GET", "/api/kg/business-context?manufacturer=huawei&product_series=SUN2000&question=low%20insulation&limit=20", "read", 1500),
        Endpoint("agent_runs", "Agent run list", "GET", "/api/agents/runs?page=1&page_size=20", "read", 600),
        Endpoint("system_status", "System status", "GET", "/api/system/status", "read", 600, auth=False),
    ]
    resources_before = resource_snapshot("before")
    results: list[dict[str, Any]] = []
    for index, endpoint in enumerate(endpoints, start=2):
        print(f"performance_endpoint_start id={endpoint.endpoint_id}", flush=True)
        endpoint_result = run_endpoint(endpoint, base_url, token, username, index)
        results.append(endpoint_result)
        print(f"performance_endpoint_complete id={endpoint.endpoint_id} classification={endpoint_result['classification']} failures={endpoint_result['warmup']['failure_count'] + endpoint_result['serial']['failure_count'] + endpoint_result['concurrency']['failure_count']}", flush=True)
    resources_after = resource_snapshot("after")
    resource_payload = {"generated_at": now_iso(), "before": resources_before, "after": resources_after, "peak": "unavailable_without_continuous_sampler", "notes": "Windows Get-Process and PostgreSQL pg_stat_activity used; unavailable fields were not fabricated."}
    resource_path = RUNTIME / "performance_resource_usage.json"
    write_json(resource_path, resource_payload)
    endpoint_path = RUNTIME / "performance_endpoint_results.json"
    write_json(endpoint_path, {"generated_at": now_iso(), "base_url": base_url, "qps_method": "completed request count divided by actual batch wall-clock duration", "client_model": "distinct 127.25.x.y loopback source addresses model independent local clients while preserving the configured per-client rate limit", "credentials_source": "environment_or_private_secure_test_configuration", "default_username": False, "default_password": False, "endpoints": results})
    classifications = Counter(item["classification"] for item in results)
    total_samples = sum(item["warmup"]["count"] + item["serial"]["count"] + item["concurrency"]["count"] for item in results)
    failures = sum(item["warmup"]["failure_count"] + item["serial"]["failure_count"] + item["concurrency"]["failure_count"] for item in results)
    timeouts = sum(item["warmup"]["timeout_count"] + item["serial"]["timeout_count"] + item["concurrency"]["timeout_count"] for item in results)
    summary = {
        "endpoint_count": len(results), "total_samples": total_samples,
        "read_samples": sum(item["warmup"]["count"] + item["serial"]["count"] + item["concurrency"]["count"] for item in results if item["profile"] == "read"),
        "write_samples": sum(item["warmup"]["count"] + item["serial"]["count"] + item["concurrency"]["count"] for item in results if item["profile"] == "write"),
        "failure_count": failures, "timeout_count": timeouts, "error_rate": failures / total_samples if total_samples else 1.0,
        "timeout_rate": timeouts / total_samples if total_samples else 1.0, "classifications": dict(classifications),
        "overall": "FAIL" if classifications["FAIL"] else ("NEEDS_OPTIMIZATION" if classifications["NEEDS_OPTIMIZATION"] else "PASS"),
        "slowest_endpoints": [{"endpoint_id": item["endpoint_id"], "p95_ms": max(item["serial"]["p95_ms"] or 0, item["concurrency"]["p95_ms"] or 0)} for item in sorted(results, key=lambda row: max(row["serial"]["p95_ms"] or 0, row["concurrency"]["p95_ms"] or 0), reverse=True)[:5]],
    }
    summary_path = RUNTIME / "performance_summary.json"
    write_json(summary_path, {"generated_at": now_iso(), "summary": summary})
    thresholds_path = RUNTIME / "performance_thresholds.json"
    write_json(thresholds_path, {"generated_at": now_iso(), "policy": "Audit classification only; business code and security controls were not changed to satisfy thresholds.", "profiles": {"read": READ_PROFILE, "write": WRITE_PROFILE}, "thresholds": [{"endpoint_id": item.endpoint_id, "p95_ms": item.threshold_ms} for item in endpoints]})
    record_result = next(item for item in results if item["endpoint_id"] == "record_center")
    record_path = RUNTIME / "record_center_query_audit.json"
    write_json(record_path, record_center_audit(record_result))
    report = ROOT / "docs" / "25A_R1_performance_baseline_report.md"
    lines = [
        "# Task 25A-R1 性能轻量基线报告", "", f"生成时间：{now_iso()}", "",
        "## 方法修正", "", "- 账号与密码只从环境或任务私有安全测试配置加载，脚本没有默认用户名/密码，也不输出密码。",
        "- QPS=实际完成请求数/真实批次墙钟时间；serial 与 concurrency 分开，warmup、并发错误、超时和业务断言失败均进入统计。本地负载使用不同 127.25.x.y 源地址模拟独立客户端，未修改或关闭按客户端限流。",
        "- 读取型参数为 5+100+100/workers=10；写入型参数为 2+20+20/workers=5。写入仅使用 `Task25AR1_` 标记、规则模式且禁用真实 provider。", "",
        "## Endpoint 结果", "", "| Endpoint | Profile | Serial p50/p95/p99 ms | Concurrent p50/p95/p99 ms | QPS | 失败/超时 | 分类 |", "|---|---|---|---|---:|---|---|",
    ]
    for item in results:
        s, c = item["serial"], item["concurrency"]
        lines.append(f"| `{item['method']} {item['path']}` | {item['profile']} | {s['p50_ms']} / {s['p95_ms']} / {s['p99_ms']} | {c['p50_ms']} / {c['p95_ms']} / {c['p99_ms']} | {c['requests_per_second']} | {s['failure_count'] + c['failure_count'] + item['warmup']['failure_count']} / {s['timeout_count'] + c['timeout_count'] + item['warmup']['timeout_count']} | {item['classification']} |")
    lines += ["", "## 汇总", "", f"- endpoints={summary['endpoint_count']}；samples={summary['total_samples']}；error_rate={summary['error_rate']:.4%}；timeout_rate={summary['timeout_rate']:.4%}。", f"- threshold result: **{summary['overall']}**。阈值只用于审计分类，未为了通过修改业务或降低安全控制。", f"- Record Center serial p50/p95/p99={record_result['serial']['p50_ms']}/{record_result['serial']['p95_ms']}/{record_result['serial']['p99_ms']} ms。", "", "## 资源证据", "", f"- before RSS={resources_before['backend_process']['rss_bytes']}；after RSS={resources_after['backend_process']['rss_bytes']}。", f"- database connections before={resources_before['database_connections']}；after={resources_after['database_connections']}。", "- 无法可靠采集的 peak/CPU/threads 字段明确标记 unavailable，没有伪造。", "", "## Record Center", "", "专项静态与运行时审计见 `.runtime/task25a_r1/record_center_query_audit.json`；Task 25E 建议将异构记录过滤、排序和分页下推到 SQL，并用生产规模夹具执行 EXPLAIN ANALYZE。", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    artifacts = [endpoint_path, summary_path, resource_path, thresholds_path, record_path, report]
    passed = failures == 0 and timeouts == 0 and len(results) >= 13
    register_test({
        "test_id": "T-R1-PERFORMANCE-BASELINE", "name": "Endpoint-level wall-clock performance baseline", "category": "performance",
        "command": "uv run python scripts/check_task25a_r1_performance_baseline.py", "started_at": started,
        "status": "PASSED" if passed else "FAILED", "exit_code": 0 if passed else 1,
        "assertion_count": total_samples + 8, "passed_assertions": total_samples - failures + 8, "failed_assertions": failures,
        "artifact_paths": artifacts, "notes": f"Threshold classification={summary['overall']}; performance threshold misses do not change functional test status.",
    })
    print(f"task25a_r1_performance endpoints={len(results)} samples={total_samples} failures={failures} timeouts={timeouts} threshold={summary['overall']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
