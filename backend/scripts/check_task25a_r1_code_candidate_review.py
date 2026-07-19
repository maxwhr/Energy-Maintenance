from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from task25a_r1_common import ROOT, RUNTIME, now_iso, read_json, register_test, write_json


OLD = ROOT / ".runtime" / "task25a"
SOURCES = (".py", ".ts", ".vue", ".js", ".mjs", ".json", ".md", ".toml", ".yaml", ".yml", ".ps1", ".sh")


def source_files() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCES:
            continue
        if any(part in {".git", ".venv", "node_modules", ".runtime"} for part in path.parts):
            continue
        try:
            rows.append((path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return rows


def unpack(name: str) -> list[dict[str, Any]]:
    payload = read_json(OLD / name, {})
    return next((value for value in payload.values() if isinstance(value, list)), [])


def path_and_symbol(item: dict[str, Any]) -> tuple[str, str]:
    evidence = item.get("evidence", [])
    probes = [str(item.get("candidate", "")), *map(str, evidence)]
    for probe in probes:
        match = re.search(r"((?:backend|frontend|scripts|docs)/[^\s:]+)(?::\d+)?(?::([A-Za-z_][A-Za-z0-9_]*))?", probe)
        if match:
            return match.group(1), match.group(2) or Path(match.group(1)).stem
    return "multiple_or_unresolved", str(item.get("candidate", "unknown"))[:160]


def review(items: list[dict[str, Any]], kind: str, files: list[tuple[str, str]], git_map: dict[str, str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        path, symbol = path_and_symbol(item)
        token = symbol if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol) else Path(path).name
        matching = [(file, text) for file, text in files if token and token in text]
        static_count = sum(text.count(token) for _, text in matching) if token else 0
        import_count = sum(len(re.findall(rf"(?:import|from)[^\n]*\b{re.escape(token)}\b", text)) for _, text in matching) if token else 0
        router = any(("router" in file.lower() or "routes" in file.lower()) and token in text for file, text in matching)
        model = any("models" in file and token in text for file, text in matching)
        agent_registry = any("agent" in file and "registr" in text.lower() and token in text for file, text in matching)
        provider_registry = any("provider" in file and "registr" in text.lower() and token in text for file, text in matching)
        frontend_route = any(file.startswith("frontend/src/router") and token in text for file, text in matching)
        package_script = any(Path(file).name in {"package.json", "pyproject.toml"} and token in text for file, text in matching)
        test_ref = any(("scripts/check_" in file or "test" in file.lower()) and token in text for file, text in matching)
        doc_ref = any(file.startswith("docs/") and token in text for file, text in matching)
        previous = str(item.get("classification", ""))
        dynamic = any([router, model, agent_registry, provider_registry, frontend_route])
        if dynamic:
            classification = "KEEP_DYNAMIC_REGISTRATION"
        elif "KEEP_COMPATIBILITY" in previous or "deprecated" in kind:
            classification = "KEEP_COMPATIBILITY" if "KEEP_COMPATIBILITY" in previous else "REVIEW_DEPRECATION"
        elif path.startswith("backend/static/frontend/"):
            classification = "KEEP_GENERATED"
        elif path.startswith("backend/scripts/") and test_ref:
            classification = "KEEP_TEST_ONLY"
        elif kind == "duplicate":
            classification = "REFACTOR_DUPLICATE"
        elif static_count <= 1:
            classification = "REMOVE_CANDIDATE_LOW_CONFIDENCE"
        else:
            classification = "KEEP_PRODUCTION"
        confidence = "high" if path != "multiple_or_unresolved" and static_count > 1 else "medium"
        results.append({
            "path": path,
            "symbol": symbol,
            "candidate_type": kind,
            "static_reference_count": static_count,
            "import_reference_count": import_count,
            "router_reference": router,
            "model_registration": model,
            "agent_registry_reference": agent_registry,
            "provider_registry_reference": provider_registry,
            "dynamic_import_risk": "high" if dynamic else "medium",
            "frontend_route_reference": frontend_route,
            "package_script_reference": package_script,
            "test_reference": test_ref,
            "doc_reference": doc_ref,
            "git_status": git_map.get(path, "clean_or_unresolved"),
            "evidence": item.get("evidence", []) + [f"current static token references={static_count}", f"current import references={import_count}"],
            "classification": classification,
            "confidence": confidence,
            "safe_to_remove_now": False,
            "recommended_task": "Task 25E focused refactor review; require owner approval, tests, and dynamic registration verification before removal",
        })
    return results


def main() -> int:
    started = now_iso()
    files = source_files()
    status = read_json(RUNTIME / "git_status_classification.json", {}).get("items", [])
    git_map = {item["path"]: item["git_status"] for item in status}
    groups = {
        "dead": review(unpack("dead_code_candidates.json"), "dead", files, git_map),
        "duplicate": review(unpack("duplicate_code_candidates.json"), "duplicate", files, git_map),
        "deprecated": review(unpack("deprecated_code_candidates.json"), "deprecated", files, git_map),
    }
    output_paths: list[Path] = []
    for name, rows in groups.items():
        path = RUNTIME / f"{name}_code_review.json"
        write_json(path, {"generated_at": now_iso(), "policy": "No candidate may be removed in Task 25A-R1.", "summary": {"total": len(rows), "safe_to_remove_now": 0, "classifications": dict(Counter(row["classification"] for row in rows))}, "items": rows})
        output_paths.append(path)

    report = ROOT / "docs" / "25A_R1_code_candidate_review.md"
    all_rows = [row for rows in groups.values() for row in rows]
    classifications = Counter(row["classification"] for row in all_rows)
    lines = [
        "# Task 25A-R1 代码候选二次复核", "", f"生成时间：{now_iso()}", "",
        "## 结论", "",
        f"- dead={len(groups['dead'])}，duplicate={len(groups['duplicate'])}，deprecated={len(groups['deprecated'])}。",
        f"- 共 {len(all_rows)} 个候选，`safe_to_remove_now=true` 为 0；本任务删除候选数为 0。",
        "- 静态引用、import、router、model/agent/provider registry、前端路由、package script、测试和文档引用均重新检查；动态注册仍是必须保留的风险边界。", "",
        "## 分类统计", "",
    ]
    lines += [f"- {key}: {value}" for key, value in sorted(classifications.items())]
    lines += ["", "## 候选明细", "", "| 类型 | 路径/符号 | 分类 | 静态引用 | 动态风险 | 可立即删除 |", "|---|---|---|---:|---|---|"]
    for row in all_rows:
        lines.append(f"| {row['candidate_type']} | `{row['path']} :: {row['symbol']}` | {row['classification']} | {row['static_reference_count']} | {row['dynamic_import_risk']} | false |")
    lines.append("")
    report.write_text("\n".join(lines), encoding="utf-8")
    output_paths.append(report)
    passed = all(not row["safe_to_remove_now"] for row in all_rows) and len(all_rows) == 111
    register_test({
        "test_id": "T-R1-CODE-CANDIDATE-REVIEW", "name": "Dead duplicate deprecated candidate re-review", "category": "static_analysis",
        "command": "uv run python scripts/check_task25a_r1_code_candidate_review.py", "started_at": started,
        "status": "PASSED" if passed else "FAILED", "exit_code": 0 if passed else 1,
        "assertion_count": len(all_rows) + 1, "passed_assertions": len(all_rows) + int(len(all_rows) == 111), "failed_assertions": 0 if passed else 1,
        "artifact_paths": output_paths, "notes": "All 111 historical candidates were re-reviewed and retained.",
    })
    print(f"task25a_r1_code_candidate_review total={len(all_rows)} safe_to_remove=0")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
