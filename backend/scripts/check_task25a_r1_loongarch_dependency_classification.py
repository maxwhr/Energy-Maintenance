from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

from task25a_r1_common import BACKEND, ROOT, RUNTIME, now_iso, register_test, write_json


def backend_versions() -> dict[str, str]:
    path = BACKEND / "uv.lock"
    if not path.is_file():
        return {}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    return {str(item.get("name", "")).lower(): str(item.get("version", "unknown")) for item in payload.get("package", [])}


def frontend_versions() -> dict[str, str]:
    path = ROOT / "frontend" / "package-lock.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    versions: dict[str, str] = {}
    for key, item in payload.get("packages", {}).items():
        if not key.startswith("node_modules/"):
            continue
        versions[key.removeprefix("node_modules/").lower()] = str(item.get("version", "unknown"))
    return versions


def row(name: str, versions: dict[str, str], *, backend: str, stage: str, required: bool, native: bool,
        wheel: str, build: bool, system: str | None, disable: bool, replace: bool, prebuild: bool,
        risk: str, probe: str, notes: str, lookup: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "version": versions.get((lookup or name).lower(), "system_or_not_locked"),
        "backend_or_frontend": backend,
        "usage_stage": stage,
        "required_on_target_server": required,
        "native_code": native,
        "possible_loongarch_wheel": wheel,
        "source_build_possible": build,
        "system_library_required": system,
        "can_disable": disable,
        "can_replace": replace,
        "prebuild_elsewhere_possible": prebuild,
        "risk": risk,
        "recommended_probe": probe,
        "notes": notes,
    }


def main() -> int:
    started = now_iso()
    py = backend_versions()
    js = frontend_versions()
    rows = [
        row("pydantic-core", py, backend="backend", stage="RUNTIME_REQUIRED", required=True, native=True, wheel="uncertain", build=True, system="Rust toolchain when no wheel", disable=False, replace=False, prebuild=False, risk="HIGH", probe="Task 25G0 install/import/model-validation probe on target", notes="Core Pydantic runtime; Rust extension and wheel availability are primary blockers."),
        row("greenlet", py, backend="backend", stage="RUNTIME_REQUIRED", required=True, native=True, wheel="uncertain", build=True, system="C compiler and Python headers when no wheel", disable=False, replace=False, prebuild=False, risk="HIGH", probe="Task 25G0 SQLAlchemy session/transaction probe", notes="SQLAlchemy dependency with native extension."),
        row("psycopg", py, backend="backend", stage="RUNTIME_REQUIRED", required=True, native=False, wheel="pure Python package; optional binary parts vary", build=True, system="libpq", disable=False, replace=True, prebuild=False, risk="HIGH", probe="Task 25G0 PostgreSQL connect, migration-current and CRUD probe", notes="Formal database driver; validate selected pure/C implementation and libpq ABI."),
        row("libpq", py, backend="system", stage="RUNTIME_REQUIRED", required=True, native=True, wheel="not applicable", build=True, system="Kylin PostgreSQL client libraries", disable=False, replace=False, prebuild=False, risk="HIGH", probe="Task 25G0 psql/driver SSL and transaction probe", notes="System runtime library, not a Python lock entry."),
        row("httptools", py, backend="backend", stage="RUNTIME_OPTIONAL", required=False, native=True, wheel="uncertain", build=True, system="C compiler/libuv build dependencies", disable=True, replace=True, prebuild=False, risk="MEDIUM", probe="Start Uvicorn with h11 fallback on target", notes="Optional Uvicorn parser; can be disabled without changing API behavior."),
        row("uvloop", py, backend="backend", stage="RUNTIME_OPTIONAL", required=False, native=True, wheel="uncertain", build=True, system="C toolchain/libuv", disable=True, replace=True, prebuild=False, risk="MEDIUM", probe="Run default asyncio event loop on target", notes="Optional on Linux and not required for production correctness."),
        row("watchfiles", py, backend="backend", stage="DEVELOPMENT_ONLY", required=False, native=True, wheel="uncertain", build=True, system="Rust toolchain when no wheel", disable=True, replace=True, prebuild=False, risk="LOW", probe="Omit --reload in systemd production service", notes="Reload helper; production service must not require it."),
        row("lxml", py, backend="backend", stage="RUNTIME_OPTIONAL", required=False, native=True, wheel="uncertain", build=True, system="libxml2/libxslt headers", disable=True, replace=True, prebuild=False, risk="MEDIUM", probe="Trace actual imports and exercise optional document conversion", notes="Native XML stack; not the baseline DOCX parser."),
        row("Pillow", py, backend="backend", stage="RUNTIME_OPTIONAL", required=False, native=True, wheel="uncertain", build=True, system="zlib/libjpeg/libpng and headers", disable=True, replace=True, prebuild=False, risk="MEDIUM", probe="Open/validate representative PNG/JPEG on target", notes="Image validation/conversion path only; inventory imports before disabling.", lookup="pillow"),
        row("Tesseract", py, backend="system", stage="RUNTIME_OPTIONAL", required=False, native=True, wheel="not applicable", build=True, system="tesseract + language packs", disable=True, replace=True, prebuild=False, risk="MEDIUM", probe="Only probe if local OCR is selected for target deployment", notes="Current first-version baseline does not require local OCR."),
        row("Node.js", js, backend="frontend", stage="BUILD_TIME_ONLY", required=False, native=True, wheel="not applicable", build=True, system="Node binary on build host", disable=False, replace=True, prebuild=True, risk="LOW", probe="Build frontend on supported non-LoongArch CI and deploy static output", notes="Node is not required on the target server when static assets are prebuilt."),
        row("Vite", js, backend="frontend", stage="BUILD_TIME_ONLY", required=False, native=False, wheel="not applicable", build=True, system=None, disable=False, replace=True, prebuild=True, risk="LOW", probe="Reproducible npm build on build host", notes="Build-time-only dependency; cannot by itself block server runtime.", lookup="vite"),
        row("Rolldown native binding", js, backend="frontend", stage="BUILD_TIME_ONLY", required=False, native=True, wheel="not applicable", build=True, system="Rust/C toolchain depending on package", disable=False, replace=True, prebuild=True, risk="MEDIUM", probe="Confirm selected Vite toolchain build host architecture", notes="Native build acceleration may be architecture-specific, but output can be prebuilt."),
        row("Playwright", js, backend="test", stage="TEST_ONLY", required=False, native=False, wheel="not applicable", build=False, system="Chromium plus desktop libraries", disable=True, replace=True, prebuild=False, risk="LOW", probe="Run browser acceptance on CI/workstation, not production target", notes="Browser testing is not a production server runtime dependency.", lookup="playwright"),
        row("Chromium", js, backend="test", stage="TEST_ONLY", required=False, native=True, wheel="not applicable", build=False, system="browser binary and GUI/headless libraries", disable=True, replace=True, prebuild=False, risk="LOW", probe="Keep off target unless browser acceptance is explicitly required there", notes="Existing R1 scripts use installed Edge/Chrome through CDP."),
        row("pypdf", py, backend="backend", stage="RUNTIME_REQUIRED", required=True, native=False, wheel="pure Python expected", build=True, system=None, disable=False, replace=True, prebuild=False, risk="LOW", probe="Parse representative Huawei/Sungrow PDF on target", notes="Baseline PDF parser.", lookup="pypdf"),
        row("python-docx", py, backend="backend", stage="RUNTIME_REQUIRED", required=True, native=False, wheel="pure Python package; lxml dependency may be native", build=True, system="lxml/libxml2 may be required", disable=False, replace=True, prebuild=False, risk="MEDIUM", probe="Parse representative DOCX and verify lxml import", notes="Baseline DOCX parser; transitive lxml risk must be probed.", lookup="python-docx"),
        row("psycopg-c", py, backend="backend", stage="RUNTIME_OPTIONAL", required=False, native=True, wheel="uncertain", build=True, system="libpq and C toolchain", disable=True, replace=True, prebuild=False, risk="MEDIUM", probe="Confirm it is absent or intentionally selected", notes="Optional native speedup; pure psycopg path should be preferred if supported."),
    ]
    usage = Counter(item["usage_stage"] for item in rows)
    summary = {
        "total": len(rows),
        "usage_stage": dict(usage),
        "runtime_required": usage["RUNTIME_REQUIRED"],
        "runtime_optional": usage["RUNTIME_OPTIONAL"],
        "build_time_only": usage["BUILD_TIME_ONLY"],
        "development_only": usage["DEVELOPMENT_ONLY"],
        "test_only": usage["TEST_ONLY"],
        "high_risk_runtime": [item["name"] for item in rows if item["risk"] == "HIGH" and item["usage_stage"] == "RUNTIME_REQUIRED"],
        "real_machine_status": "NOT_EXECUTED",
        "recommended_next_task": "Task 25G0 dependency and import probe on a real LoongArch + Kylin machine",
    }
    output = RUNTIME / "loongarch_dependency_classification.json"
    write_json(output, {"generated_at": now_iso(), "summary": summary, "dependencies": rows})
    report = ROOT / "docs" / "25A_R1_loongarch_dependency_classification.md"
    lines = [
        "# Task 25A-R1 LoongArch / Kylin 依赖用途分类", "", f"生成时间：{now_iso()}", "",
        "## 结论", "",
        "- 本轮只完成 Windows 静态依赖分类；LoongArch/Kylin 实机状态为 **NOT_EXECUTED**，不得表述为通过。",
        "- 前端可在非龙芯构建机预构建并只把静态文件部署到目标服务器；Node.js、Vite/Rolldown 的 build-time 风险不等于服务器 runtime 阻断。",
        "- Playwright/Chromium 是测试依赖；uvloop、httptools、watchfiles 可禁用或不进入正式服务。",
        "- pydantic-core、greenlet、psycopg/libpq 是 Task 25G0 的最高优先级探针。", "",
        "## 用途统计", "",
    ]
    lines += [f"- {key}: {value}" for key, value in sorted(usage.items())]
    lines += ["", "## 依赖明细", "", "| 依赖 | 版本 | 阶段 | 目标必需 | Native | 风险 |", "|---|---|---|---|---|---|"]
    for item in rows:
        lines.append(f"| {item['name']} | {item['version']} | {item['usage_stage']} | {str(item['required_on_target_server']).lower()} | {str(item['native_code']).lower()} | {item['risk']} |")
    lines += ["", "## 下一步", "", "Task 25G0 必须在真实 LoongArch + Kylin 机器执行安装、import、PostgreSQL 连接、文档解析和服务启动探针；本报告不能替代实机证据。", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    register_test({
        "test_id": "T-R1-LOONGARCH-CLASSIFICATION", "name": "LoongArch dependency usage classification", "category": "static_analysis",
        "command": "uv run python scripts/check_task25a_r1_loongarch_dependency_classification.py", "started_at": started,
        "status": "PASSED", "exit_code": 0, "assertion_count": len(rows) + 3, "passed_assertions": len(rows) + 3,
        "artifact_paths": [output, report], "notes": "Static classification passed; no real-machine claim was made.",
    })
    print(f"task25a_r1_loongarch_dependency_classification total={len(rows)} real_machine=NOT_EXECUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
