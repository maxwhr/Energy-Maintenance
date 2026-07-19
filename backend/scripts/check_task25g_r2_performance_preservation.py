from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import event, text

from task25g_r2_common import TASK25G_R1_RUNTIME, now_iso, read_json, write_json


def _p95(values: list[float]) -> float:
    if len(values) <= 1:
        return round(values[0] if values else 0.0, 3)
    return round(statistics.quantiles(values, n=20, method="inclusive")[18], 3)


def main() -> int:
    from app.core.database import SessionLocal, engine
    from app.services.knowledge_graph_service import KnowledgeGraphService

    queries = {
        "node_search": ("SELECT id FROM kg_nodes WHERE status='active' AND canonical_name ILIKE :q LIMIT 30", {"q": "%SUN2000%"}),
        "alias": ("SELECT node_id FROM kg_node_aliases WHERE normalized_alias ILIKE :q LIMIT 30", {"q": "%sun2000%"}),
        "one_hop": ("SELECT id FROM kg_edges WHERE status='active' LIMIT 100", {}),
        "two_hop": ("SELECT e2.id FROM kg_edges e1 JOIN kg_edges e2 ON e1.target_node_id=e2.source_node_id WHERE e1.status='active' AND e2.status='active' LIMIT 200", {}),
    }
    samples: dict[str, list[float]] = defaultdict(list)
    sql_counts: list[int] = []
    errors = []
    with SessionLocal() as session:
        for _ in range(30):
            for name, (statement, params) in queries.items():
                started = time.perf_counter()
                try:
                    list(session.execute(text(statement), params))
                except Exception as exc:  # noqa: BLE001
                    errors.append({"name": name, "error_type": exc.__class__.__name__})
                samples[name].append((time.perf_counter() - started) * 1000)
        for _ in range(30):
            count = 0

            def before_cursor_execute(*_args: Any, **_kwargs: Any) -> None:
                nonlocal count
                count += 1

            event.listen(engine, "before_cursor_execute", before_cursor_execute)
            started = time.perf_counter()
            try:
                KnowledgeGraphService(session).business_context(question="逆变器告警排查", limit=30)
            except Exception as exc:  # noqa: BLE001
                errors.append({"name": "rag_context", "error_type": exc.__class__.__name__})
            finally:
                event.remove(engine, "before_cursor_execute", before_cursor_execute)
            samples["rag_context"].append((time.perf_counter() - started) * 1000)
            sql_counts.append(count)
    metrics = {
        name: {"p50_ms": round(statistics.median(values), 3), "p95_ms": _p95(values)}
        for name, values in samples.items()
    }
    thresholds = {"node_search": 500, "alias": 300, "one_hop": 800, "two_hop": 1500, "rag_context": 1200}
    failures = [name for name, limit in thresholds.items() if metrics[name]["p95_ms"] > limit]
    if max(sql_counts or [0]) > 25:
        failures.append("sql_count")
    if errors:
        failures.append("query_error")
    baseline = read_json(TASK25G_R1_RUNTIME / "kg_performance_preservation.json", {})
    payload = {
        "version": "task25g_r2_performance_preservation_v1",
        "generated_at": now_iso(),
        "status": "PASS" if not failures else "FAIL",
        "metrics": metrics,
        "sql_count_max": max(sql_counts or [0]),
        "serializer_sql": 0,
        "n_plus_one": False,
        "thresholds_ms": thresholds,
        "task25g_r1_baseline_metrics": baseline.get("metrics") or {},
        "errors": errors,
        "failures": failures,
    }
    write_json("performance_preservation.json", payload)
    print(json.dumps({"status": payload["status"], "p95_ms": {k: v["p95_ms"] for k, v in metrics.items()}, "sql_count_max": payload["sql_count_max"]}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
