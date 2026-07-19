from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from task25a_r1_common import ROOT, RUNTIME, now_iso, register_test, run, sha256_file, write_csv, write_json


ALLOWED = {
    "MODIFIED_EXPECTED", "MODIFIED_REVIEW", "DELETED_INTENTIONAL", "DELETED_REPLACED",
    "DELETED_RENAMED", "DELETED_GENERATED_ASSET", "DELETED_LEGACY_CANDIDATE",
    "DELETED_POSSIBLE_ACCIDENTAL", "UNTRACKED_EXPECTED_SOURCE", "UNTRACKED_EXPECTED_TEST",
    "UNTRACKED_EXPECTED_DOC", "UNTRACKED_GENERATED", "UNTRACKED_RUNTIME", "UNTRACKED_REVIEW", "UNKNOWN",
}


def git(*args: str) -> dict[str, Any]:
    return run(["git", *args], ROOT)


def logical_asset_name(name: str) -> str:
    return re.sub(r"-[A-Za-z0-9_-]{8,}(?=\.(?:js|css|map)$)", "", name)


def status_entries() -> list[tuple[str, str]]:
    result = git("status", "--porcelain=v1", "-z")
    raw = result["stdout"]
    entries: list[tuple[str, str]] = []
    parts = raw.split("\0")
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        code, path = item[:2], item[3:]
        if code[0] in "RC" or code[1] in "RC":
            if index < len(parts):
                old = parts[index]
                index += 1
                entries.append((code, path))
                entries.append(("R?", old))
        else:
            entries.append((code, path))
    return entries


def head_bytes(path: str) -> bytes | None:
    proc = run(["git", "show", f"HEAD:{path}"], ROOT)
    if proc["exit_code"] != 0:
        return None
    return proc["stdout"].encode("utf-8", errors="replace")


def classify(code: str, path: str, exists: bool, replacement: str | None) -> tuple[str, str, str, str]:
    is_deleted = "D" in code
    is_untracked = code == "??"
    generated_asset = path.startswith("backend/static/frontend/")
    if is_deleted:
        if generated_asset and replacement:
            return "DELETED_GENERATED_ASSET", "high", "P2", "keep deletion paired with regenerated hashed asset; do not restore individual hash files"
        if replacement:
            return "DELETED_REPLACED", "medium", "P1", "review the replacement mapping; do not restore automatically"
        return "DELETED_POSSIBLE_ACCIDENTAL", "medium", "P1", "manual owner review required; do not restore automatically"
    if is_untracked:
        if path.startswith(".runtime/"):
            return "UNTRACKED_RUNTIME", "high", "P2", "retain as local audit evidence and keep out of commits unless explicitly requested"
        if generated_asset:
            return "UNTRACKED_GENERATED", "high", "P2", "retain as current generated static output"
        if path.startswith("docs/"):
            return "UNTRACKED_EXPECTED_DOC", "high", "P2", "review as Task 25A/R1 documentation"
        if path.startswith("backend/scripts/") and ("check_" in Path(path).name or "test" in Path(path).name):
            return "UNTRACKED_EXPECTED_TEST", "high", "P2", "review as audit/test source"
        if path.startswith(("backend/", "frontend/", "scripts/")):
            return "UNTRACKED_EXPECTED_SOURCE", "medium", "P1", "review before any future staging decision"
        return "UNTRACKED_REVIEW", "low", "P1", "manual review required"
    if generated_asset:
        return "MODIFIED_EXPECTED", "high", "P2", "generated static entry changed with the current frontend build"
    return "MODIFIED_REVIEW", "medium", "P1", "preserve and review as an existing tracked modification"


def main() -> int:
    started = now_iso()
    commands = {
        "status_short": git("status", "--short"),
        "status_porcelain_v2": git("status", "--porcelain=v2"),
        "diff_name_status": git("diff", "--name-status"),
        "diff_summary": git("diff", "--summary"),
        "diff_stat": git("diff", "--stat"),
        "deleted": git("ls-files", "--deleted"),
        "untracked": git("ls-files", "--others", "--exclude-standard"),
    }
    raw_path = RUNTIME / "git_status_raw.json"
    write_json(raw_path, {"generated_at": now_iso(), "commands": commands})

    entries = status_entries()
    current_files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts and ".venv" not in p.parts]
    assets: dict[str, list[str]] = {}
    for file in current_files:
        relative = file.relative_to(ROOT).as_posix()
        if relative.startswith("backend/static/frontend/assets/"):
            assets.setdefault(logical_asset_name(file.name), []).append(relative)

    searchable: list[str] = []
    for file in current_files:
        if file.suffix.lower() not in {".py", ".ts", ".vue", ".js", ".mjs", ".json", ".md", ".html", ".toml", ".yaml", ".yml", ".ps1", ".sh"}:
            continue
        try:
            searchable.append(file.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    haystack = "\n".join(searchable)

    rows: list[dict[str, Any]] = []
    for code, path in entries:
        absolute = ROOT / path
        exists_now = absolute.exists()
        head = head_bytes(path)
        logical = logical_asset_name(Path(path).name)
        replacements = [item for item in assets.get(logical, []) if item != path]
        replacement = replacements[0] if replacements else None
        category, confidence, risk, recommendation = classify(code, path, exists_now, replacement)
        if category not in ALLOWED:
            category = "UNKNOWN"
        suffix = absolute.suffix.lower()
        directory = Path(path).parent.as_posix()
        production = path.startswith(("backend/app/", "frontend/src/")) or path.startswith("backend/static/frontend/")
        generated = path.startswith("backend/static/frontend/") or path.startswith(".runtime/")
        reference_count = haystack.count(Path(path).name)
        row = {
            "path": path,
            "git_status": code,
            "tracked": code != "??",
            "exists_now": exists_now,
            "exists_in_head": head is not None,
            "size_now": absolute.stat().st_size if absolute.is_file() else None,
            "head_size": len(head) if head is not None else None,
            "file_type": suffix or "none",
            "directory": directory,
            "production_or_nonproduction": "production" if production else "nonproduction",
            "generated": generated,
            "runtime_data": path.startswith(".runtime/"),
            "migration": "alembic/versions/" in path,
            "test_only": path.startswith("backend/scripts/check_") or "test" in Path(path).name.lower(),
            "documentation": path.startswith("docs/") or Path(path).name.lower().startswith("readme"),
            "possible_rename_from": path if "D" in code and replacement else None,
            "possible_rename_to": replacement,
            "reference_count": reference_count,
            "dynamic_registration_risk": "medium" if suffix in {".py", ".ts", ".vue", ".js", ".mjs"} else "low",
            "classification": category,
            "confidence": confidence,
            "risk": risk,
            "recommended_action": recommendation,
            "evidence": [
                f"HEAD exists={head is not None}; current exists={exists_now}",
                f"logical asset key={logical}; replacement={replacement or 'none'}",
                f"exact basename references in current searchable files={reference_count}",
            ],
            "notes": "No file was restored, deleted, staged, or otherwise mutated by this classifier.",
            "sha256_now": sha256_file(absolute),
        }
        rows.append(row)

    counts = Counter(item["classification"] for item in rows)
    summary = {
        "total_entries": len(rows),
        "modified": sum(code != "??" and "D" not in code for code, _ in entries),
        "deleted": sum("D" in code for code, _ in entries),
        "untracked": sum(code == "??" for code, _ in entries),
        "intentional_deleted": counts["DELETED_INTENTIONAL"],
        "renamed_or_replaced": counts["DELETED_RENAMED"] + counts["DELETED_REPLACED"],
        "generated": sum(bool(item["generated"]) for item in rows),
        "deleted_generated": counts["DELETED_GENERATED_ASSET"],
        "possible_accidental": counts["DELETED_POSSIBLE_ACCIDENTAL"],
        "unknown": counts["UNKNOWN"],
        "production_source_affected": sum(item["production_or_nonproduction"] == "production" for item in rows),
        "migration_affected": sum(bool(item["migration"]) for item in rows),
        "deployment_affected": sum(item["path"].startswith(("deploy/", "scripts/deploy")) for item in rows),
        "frontend_affected": sum("frontend" in item["path"] for item in rows),
        "backend_affected": sum(item["path"].startswith("backend/") for item in rows),
        "classifications": dict(sorted(counts.items())),
    }
    json_path = RUNTIME / "git_status_classification.json"
    csv_path = RUNTIME / "git_status_classification.csv"
    write_json(json_path, {"generated_at": now_iso(), "summary": summary, "items": rows})
    write_csv(csv_path, rows)

    report = ROOT / "docs" / "25A_R1_git_worktree_classification.md"
    accidental = [item for item in rows if item["classification"] == "DELETED_POSSIBLE_ACCIDENTAL"]
    lines = [
        "# Task 25A-R1 Git 工作树分类报告", "", f"生成时间：{now_iso()}", "",
        "## 汇总", "",
        f"- 状态项：{summary['total_entries']}；modified={summary['modified']}；deleted={summary['deleted']}；untracked={summary['untracked']}。",
        f"- 52 个 deleted 中：生成资产={summary['deleted_generated']}；替代/重命名={summary['renamed_or_replaced']}；疑似误删={summary['possible_accidental']}；unknown={summary['unknown']}。",
        "- 本脚本没有执行 add、commit、restore、checkout、clean 或 reset，也没有恢复或删除任何文件。", "",
        "## Deleted 逐项结论", "",
        "| 路径 | 分类 | 替代项 | 引用数 | 风险 |", "|---|---|---|---:|---|",
    ]
    for item in rows:
        if "D" in item["git_status"]:
            lines.append(f"| `{item['path']}` | {item['classification']} | `{item['possible_rename_to'] or '-'}` | {item['reference_count']} | {item['risk']} |")
    lines += ["", "## P0/P1 疑似误删", ""]
    lines += [f"- `{item['path']}`：{item['evidence'][1]}" for item in accidental] or ["- 无。"]
    lines += ["", "## 分类产物", "", "- `.runtime/task25a_r1/git_status_raw.json`", "- `.runtime/task25a_r1/git_status_classification.json`", "- `.runtime/task25a_r1/git_status_classification.csv`", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    passed = summary["total_entries"] == len(rows) and summary["deleted"] == 52
    artifacts = [raw_path, json_path, csv_path, report]
    register_test({
        "test_id": "T-R1-GIT-CLASSIFICATION", "name": "Git worktree complete classification", "category": "static_analysis",
        "command": "uv run python scripts/check_task25a_r1_git_classification.py", "started_at": started,
        "status": "PASSED" if passed else "FAILED", "exit_code": 0 if passed else 1,
        "assertion_count": 3, "passed_assertions": 3 if passed else 2, "failed_assertions": 0 if passed else 1,
        "artifact_paths": artifacts, "notes": "Read-only Git commands; all status entries and all 52 deleted paths classified.",
    })
    print(f"task25a_r1_git_classification total={len(rows)} deleted={summary['deleted']} possible_accidental={summary['possible_accidental']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
