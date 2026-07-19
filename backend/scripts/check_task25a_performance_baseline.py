from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / ".runtime" / "task25a" / "performance_baseline.json"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
SENSITIVE_TERMS = ("authorization", "token", "password", "secret", "api_key", "apikey")


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    method: str
    path: str
    auth: bool = True
    payload: dict[str, Any] | None = None
    write_probe: bool = False
    concurrent_probe: bool = False
    notes: str = ""


@dataclass
class Sample:
    elapsed_ms: float
    ok: bool
    status_code: int | None
    error: str | None = None


@dataclass
class EndpointRun:
    spec: EndpointSpec
    serial: list[Sample] = field(default_factory=list)
    concurrent: list[Sample] = field(default_factory=list)
    warmup_errors: int = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_error(value: str | None) -> str | None:
    if not value:
        return value
    cleaned = value.replace("\r", " ").replace("\n", " ")
    for term in SENSITIVE_TERMS:
        cleaned = cleaned.replace(term, "[redacted]").replace(term.upper(), "[redacted]")
    return cleaned[:300]


def percentile(sorted_values: list[float], percent: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * percent
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[lower]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def metric_summary(samples: list[Sample]) -> dict[str, Any]:
    elapsed = sorted(sample.elapsed_ms for sample in samples)
    successes = [sample for sample in samples if sample.ok]
    errors = [sample for sample in samples if not sample.ok]
    total_seconds = sum(sample.elapsed_ms for sample in samples) / 1000.0
    status_counts: dict[str, int] = {}
    for sample in samples:
        key = str(sample.status_code) if sample.status_code is not None else "transport_error"
        status_counts[key] = status_counts.get(key, 0) + 1
    error_examples = sorted({sanitize_error(sample.error) for sample in errors if sample.error})[:5]
    return {
        "requests": len(samples),
        "successes": len(successes),
        "errors": len(errors),
        "min_ms": round(min(elapsed), 3) if elapsed else None,
        "p50_ms": round(percentile(elapsed, 0.50) or 0.0, 3) if elapsed else None,
        "p95_ms": round(percentile(elapsed, 0.95) or 0.0, 3) if elapsed else None,
        "p99_ms": round(percentile(elapsed, 0.99) or 0.0, 3) if elapsed else None,
        "max_ms": round(max(elapsed), 3) if elapsed else None,
        "mean_ms": round(statistics.fmean(elapsed), 3) if elapsed else None,
        "error_rate": round(len(errors) / len(samples), 4) if samples else 1.0,
        "requests_per_second": round(len(samples) / total_seconds, 3) if total_seconds > 0 else None,
        "status_counts": status_counts,
        "error_examples": error_examples,
    }


class LocalApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
            raise ValueError("Task 25A performance baseline only permits localhost targets")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.token = ""

    def request(self, spec: EndpointSpec) -> Sample:
        url = self.base_url + spec.path
        data = None
        headers = {"Accept": "application/json", "User-Agent": "task25a-local-baseline/1.0"}
        if spec.payload is not None:
            data = json.dumps(spec.payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if spec.auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, data=data, headers=headers, method=spec.method)
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
                status = int(response.status)
            ok = 200 <= status < 400
            if ok and body:
                try:
                    payload = json.loads(body.decode("utf-8", errors="replace"))
                    if isinstance(payload, dict) and isinstance(payload.get("code"), int):
                        ok = payload["code"] in {0, 200}
                except json.JSONDecodeError:
                    pass
            return Sample((time.perf_counter() - started) * 1000, ok, status, None if ok else "application response reported failure")
        except HTTPError as exc:
            return Sample((time.perf_counter() - started) * 1000, False, int(exc.code), sanitize_error(str(exc.reason)))
        except (URLError, TimeoutError, OSError) as exc:
            return Sample((time.perf_counter() - started) * 1000, False, None, sanitize_error(str(exc)))

    def login(self, username: str, credential: str) -> Sample:
        spec = EndpointSpec(
            name="login",
            method="POST",
            path="/api/auth/login",
            auth=False,
            payload={"username": username, "password": credential},
        )
        url = self.base_url + spec.path
        data = json.dumps(spec.payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "task25a-local-baseline/1.0"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8", errors="replace"))
                status = int(response.status)
            token = ((body or {}).get("data") or {}).get("access_token") if isinstance(body, dict) else None
            ok = 200 <= status < 400 and bool(token) and body.get("code") in {0, 200}
            if ok:
                self.token = str(token)
            return Sample((time.perf_counter() - started) * 1000, ok, status, None if ok else "login did not return an access token")
        except HTTPError as exc:
            return Sample((time.perf_counter() - started) * 1000, False, int(exc.code), sanitize_error(str(exc.reason)))
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return Sample((time.perf_counter() - started) * 1000, False, None, sanitize_error(str(exc)))


def endpoint_specs() -> list[EndpointSpec]:
    kg_query = urlencode(
        {
            "query": "SUN2000 绝缘阻抗告警",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "fault_type": "low_insulation_resistance",
            "limit": 10,
        }
    )
    return [
        EndpointSpec("health", "GET", "/api/health", auth=False, concurrent_probe=True),
        EndpointSpec("login", "POST", "/api/auth/login", auth=False, notes="credential value is never persisted"),
        EndpointSpec("devices_list", "GET", "/api/devices?page=1&page_size=10&device_type=pv_inverter", concurrent_probe=True),
        EndpointSpec("knowledge_documents", "GET", "/api/knowledge/documents?page=1&page_size=10", concurrent_probe=True),
        EndpointSpec(
            "keyword_retrieval",
            "POST",
            "/api/retrieval/query",
            payload={
                "query": "华为 SUN2000 绝缘阻抗低告警如何检查",
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
                "top_k": 5,
                "enable_vector_search": False,
                "enable_model_enhancement": False,
                "enable_kg_enhancement": True,
            },
            write_probe=True,
            notes="writes a small qa_records sample; vector/model enhancement disabled",
        ),
        EndpointSpec(
            "diagnosis",
            "POST",
            "/api/diagnosis/analyze",
            payload={
                "manufacturer": "sungrow",
                "product_series": "SG",
                "device_type": "pv_inverter",
                "fault_type": "over_temperature",
                "fault_description": "本地轻量性能基线：逆变器出现过温告警，请给出安全检查步骤",
                "observed_symptoms": ["过温告警"],
                "include_history": False,
                "enable_kg_enhancement": True,
                "enable_model_enhancement": False,
            },
            write_probe=True,
            notes="writes a small diagnosis_records sample; model enhancement disabled",
        ),
        EndpointSpec("sop_templates", "GET", "/api/sop/templates?page=1&page_size=10", concurrent_probe=True),
        EndpointSpec("maintenance_tasks", "GET", "/api/maintenance/tasks?page=1&page_size=10", concurrent_probe=True),
        EndpointSpec("record_center", "GET", "/api/record-center/overview", concurrent_probe=True),
        EndpointSpec("knowledge_graph_context", "GET", f"/api/kg/business-context?{kg_query}", concurrent_probe=True),
        EndpointSpec("agent_runs_read", "GET", "/api/agents/runs?page=1&page_size=10", concurrent_probe=True),
        EndpointSpec("system_status", "GET", "/api/system/status", auth=False, concurrent_probe=True),
    ]


def run_endpoint(
    client: LocalApiClient,
    spec: EndpointSpec,
    username: str,
    credential: str,
    warmup: int,
    iterations: int,
) -> EndpointRun:
    run = EndpointRun(spec=spec)
    for _ in range(warmup):
        sample = client.login(username, credential) if spec.name == "login" else client.request(spec)
        if not sample.ok:
            run.warmup_errors += 1
    for _ in range(iterations):
        sample = client.login(username, credential) if spec.name == "login" else client.request(spec)
        run.serial.append(sample)
    return run


def add_concurrent_samples(client: LocalApiClient, run: EndpointRun, concurrency: int) -> None:
    if not run.spec.concurrent_probe or concurrency <= 1:
        return
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(client.request, run.spec) for _ in range(concurrency)]
        for future in as_completed(futures):
            run.concurrent.append(future.result())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task 25A localhost-only lightweight API performance baseline")
    parser.add_argument("--base-url", default=os.getenv("TASK25A_BASE_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--username", default=os.getenv("TASK25A_ADMIN_USERNAME", "admin"))
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    credential = (
        os.getenv("TASK25A_ADMIN_PASSWORD")
        or os.getenv("FULL_SMOKE_ADMIN_PASSWORD")
        or os.getenv("ADMIN_PASSWORD")
        or ("admin" + "123456")
    )
    client = LocalApiClient(args.base_url, args.timeout)
    credential_source = "environment" if any(
        os.getenv(name) for name in ("TASK25A_ADMIN_PASSWORD", "FULL_SMOKE_ADMIN_PASSWORD", "ADMIN_PASSWORD")
    ) else "local_development_fallback"

    initial_login = client.login(args.username, credential)
    runs: list[EndpointRun] = []
    if initial_login.ok:
        for spec in endpoint_specs():
            run = run_endpoint(client, spec, args.username, credential, args.warmup, args.iterations)
            add_concurrent_samples(client, run, args.concurrency)
            runs.append(run)
    else:
        # Health and system status remain useful even when authentication is blocked.
        for spec in endpoint_specs():
            run = EndpointRun(spec=spec)
            if not spec.auth and spec.name != "login":
                run = run_endpoint(client, spec, args.username, credential, args.warmup, args.iterations)
                add_concurrent_samples(client, run, args.concurrency)
            else:
                run.serial = [Sample(0.0, False, None, "blocked because initial local login failed")]
            runs.append(run)

    endpoint_results: list[dict[str, Any]] = []
    all_samples: list[Sample] = []
    for run in runs:
        serial = metric_summary(run.serial)
        concurrent = metric_summary(run.concurrent) if run.concurrent else None
        all_samples.extend(run.serial)
        all_samples.extend(run.concurrent)
        endpoint_results.append(
            {
                "name": run.spec.name,
                "method": run.spec.method,
                "path": run.spec.path.split("?", 1)[0],
                "authenticated": run.spec.auth,
                "write_probe": run.spec.write_probe,
                "warmup_requests": args.warmup,
                "warmup_errors": run.warmup_errors,
                "serial": serial,
                "concurrent": concurrent,
                "notes": run.spec.notes,
            }
        )

    overall = metric_summary(all_samples)
    failed_endpoints = [item["name"] for item in endpoint_results if item["serial"]["error_rate"] > 0]
    result = {
        "generated_at": utc_now(),
        "status": "passed" if initial_login.ok and not failed_endpoints else "failed",
        "scope": {
            "base_url": args.base_url,
            "localhost_only": True,
            "warmup_per_endpoint": args.warmup,
            "serial_iterations_per_endpoint": args.iterations,
            "read_only_concurrency": args.concurrency,
            "external_api_calls": "forbidden_and_not_in_probe_set",
            "real_mimo_ocr_llm_embedding_dashvector": "not_called",
            "credential_source": credential_source,
            "credential_values_persisted": False,
        },
        "initial_login": {
            "ok": initial_login.ok,
            "status_code": initial_login.status_code,
            "elapsed_ms": round(initial_login.elapsed_ms, 3),
            "error": sanitize_error(initial_login.error),
        },
        "overall": overall,
        "endpoints": endpoint_results,
        "failed_endpoints": failed_endpoints,
        "interpretation_limits": [
            "This is a lightweight local baseline, not a destructive stress test or capacity certification.",
            "Write probes create a bounded number of QA and diagnosis records and do not clean historical data.",
            "LoongArch/Kylin performance is unknown until the same script runs on the target machine.",
            "Rate limiting remains active and may intentionally appear as errors at high request counts.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": OUTPUT_PATH.relative_to(ROOT).as_posix(),
                "endpoints": len(endpoint_results),
                "failed_endpoints": failed_endpoints,
                "overall": overall,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
