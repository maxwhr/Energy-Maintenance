from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / ".runtime" / "task25a"

INVENTORY_ROOTS = (
    ROOT / "README.md",
    ROOT / "backend",
    ROOT / "frontend",
    ROOT / "scripts",
    ROOT / "docs",
    ROOT / "storage",
    ROOT / "delivery",
    ROOT / "delivery_staging",
)
SKIP_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
SOURCE_SUFFIXES = {".py", ".ts", ".vue", ".js", ".mjs", ".ps1", ".sh"}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {
    ".css",
    ".html",
    ".json",
    ".md",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
GENERATED_SUFFIXES = {".map", ".tsbuildinfo", ".pyc"}
NATIVE_DEPENDENCY_HINTS = {
    "httptools": "native extension; wheel availability must be confirmed on LoongArch",
    "greenlet": "native extension used by SQLAlchemy; LoongArch wheel or compiler toolchain must be confirmed",
    "lxml": "native XML extension required by python-docx; libxml2/libxslt headers and a LoongArch build may be required",
    "psycopg": "pure-Python package still requires a usable libpq implementation on the target host",
    "pyyaml": "contains an optional C extension; source build behavior must be verified",
    "uvloop": "native extension and platform-specific event loop; optional on unsupported platforms",
    "watchfiles": "Rust/native extension; LoongArch wheel availability may require source build",
    "websockets": "may use optimized native components depending on release; runtime install must be verified",
    "psycopg-c": "native extension variant; prefer pure Python or verify target build toolchain",
    "psycopg-binary": "prebuilt native wheel; LoongArch availability must be confirmed",
    "pillow": "native image codecs; target system libraries and wheels must be confirmed",
    "cryptography": "Rust/native extension; target wheel or Rust toolchain may be required",
    "pydantic-core": "Rust extension; LoongArch wheel availability is a hard installation check",
    "orjson": "Rust/native extension; optional but target wheel availability must be confirmed",
    "tesseract": "external executable/system package; not a Python-only dependency",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def git_path_set(*args: str) -> set[str]:
    output = run_git(*args)
    return {item.replace("\\", "/") for item in output.split("\0") if item}


def is_private_runtime_path(path: Path) -> bool:
    relative = rel(path)
    parts = set(path.parts)
    if path.name == ".env":
        return True
    if "storage" in parts and path.name != ".gitkeep":
        return True
    if relative.startswith("logs/"):
        return True
    return False


def iter_inventory_files() -> tuple[list[Path], dict[str, Any]]:
    files: list[Path] = []
    skipped = Counter()
    private_directory_counts: Counter[str] = Counter()

    for scan_root in INVENTORY_ROOTS:
        if not scan_root.exists():
            skipped[f"missing:{rel(scan_root)}"] += 1
            continue
        if scan_root.is_file():
            files.append(scan_root)
            continue
        for directory, directory_names, file_names in os.walk(scan_root):
            directory_names.sort(key=str.lower)
            file_names.sort(key=str.lower)
            retained_directories: list[str] = []
            for name in directory_names:
                if name in SKIP_DIRECTORY_NAMES:
                    skipped[f"directory:{name.lower()}"] += 1
                else:
                    retained_directories.append(name)
            directory_names[:] = retained_directories
            directory_path = Path(directory)
            for name in file_names:
                path = directory_path / name
                if is_private_runtime_path(path):
                    top = rel(path).split("/", 1)[0]
                    private_directory_counts[top] += 1
                    continue
                files.append(path)

    unique_files = sorted(set(files), key=lambda item: rel(item).lower())
    privacy = {
        "policy": "storage/log/private environment file contents were not read",
        "private_files_not_content_scanned": sum(private_directory_counts.values()),
        "private_directory_file_counts": dict(sorted(private_directory_counts.items())),
        "excluded_directory_observations": dict(sorted(skipped.items())),
    }
    return unique_files, privacy


def classify_path(path: Path) -> str:
    relative = rel(path)
    suffix = path.suffix.lower()

    if relative.startswith("delivery/") or relative.startswith("delivery_staging/"):
        return "historical_delivery_file"
    if relative.startswith("frontend_legacy") or "legacy" in path.name.lower():
        return "possible_deprecated_file"
    if relative.startswith("backend/static/frontend/") or relative.startswith("frontend/dist/"):
        return "static_build_artifact"
    if relative.startswith("backend/alembic/versions/"):
        return "migration"
    if relative.startswith("backend/app/") and suffix == ".py":
        return "backend_production_code"
    if relative.startswith("frontend/src/") and suffix in {".ts", ".vue", ".css"}:
        return "frontend_production_code"
    if relative.startswith("backend/scripts/"):
        if path.name.startswith("check_") or suffix == ".mjs":
            return "test_or_audit_script"
        return "local_operations_script"
    if relative.startswith("scripts/"):
        return "local_operations_or_smoke_script"
    if relative.startswith("docs/") or path.name in {"README.md", "AGENTS.md"}:
        return "documentation"
    if path.name.startswith("seed_") or "sample" in relative.lower():
        return "sample_data_or_seed"
    if suffix in GENERATED_SUFFIXES:
        return "generated_asset"
    if relative.startswith(".runtime/") or relative.startswith("logs/"):
        return "runtime_file"
    if path.name.endswith(("~", ".tmp", ".temp")):
        return "temporary_file"
    return "project_support_file"


def safe_line_count(path: Path) -> int | None:
    if path.suffix.lower() not in TEXT_SUFFIXES or is_private_runtime_path(path):
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def read_text(path: Path) -> str:
    if is_private_runtime_path(path):
        raise ValueError(f"refusing to read private runtime content: {rel(path)}")
    return path.read_text(encoding="utf-8", errors="replace")


def write_json(name: str, payload: Any) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / name
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def project_file_inventory(files: list[Path], privacy: dict[str, Any]) -> dict[str, Any]:
    tracked = git_path_set("ls-files", "-z")
    untracked = git_path_set("ls-files", "--others", "--exclude-standard", "-z")
    categories: Counter[str] = Counter()
    extensions: Counter[str] = Counter()
    directories: Counter[str] = Counter()
    entries: list[dict[str, Any]] = []

    for path in files:
        relative = rel(path)
        category = classify_path(path)
        categories[category] += 1
        extensions[path.suffix.lower() or "<no_extension>"] += 1
        directories[relative.split("/", 1)[0]] += 1
        stat = path.stat()
        entries.append(
            {
                "path": relative,
                "category": category,
                "size_bytes": stat.st_size,
                "tracked": relative in tracked,
                "untracked": relative in untracked,
            }
        )

    return {
        "generated_at": utc_now(),
        "scope": [rel(item) for item in INVENTORY_ROOTS],
        "summary": {
            "files_inventoried": len(entries),
            "tracked_files_in_scope": sum(1 for item in entries if item["tracked"]),
            "untracked_files_in_scope": sum(1 for item in entries if item["untracked"]),
            "generated_assets": categories["static_build_artifact"] + categories["generated_asset"],
            "categories": dict(sorted(categories.items())),
            "extensions": dict(sorted(extensions.items())),
            "top_level_distribution": dict(sorted(directories.items())),
        },
        "privacy": privacy,
        "files": entries,
    }


def python_ast_metrics(path: Path) -> dict[str, int]:
    metrics = Counter()
    try:
        tree = ast.parse(read_text(path), filename=rel(path))
    except (OSError, SyntaxError, ValueError):
        metrics["parse_errors"] += 1
        return dict(metrics)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics["functions"] += 1
            if isinstance(node, ast.AsyncFunctionDef):
                metrics["async_functions"] += 1
        elif isinstance(node, ast.ClassDef):
            metrics["classes"] += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            metrics["imports"] += 1
        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                metrics["bare_except"] += 1
            elif isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
                metrics["broad_except"] += 1
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"execute", "exec_driver_sql"}:
                metrics["sql_execute_calls"] += 1
    return dict(metrics)


def project_code_inventory(files: list[Path]) -> dict[str, Any]:
    totals = Counter()
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    by_language: dict[str, Counter[str]] = defaultdict(Counter)
    ast_totals = Counter()
    file_metrics: list[dict[str, Any]] = []
    language_by_suffix = {
        ".py": "python",
        ".ts": "typescript",
        ".vue": "vue",
        ".js": "javascript",
        ".mjs": "javascript_module",
        ".ps1": "powershell",
        ".sh": "shell",
        ".css": "css",
        ".html": "html",
    }

    for path in files:
        suffix = path.suffix.lower()
        if suffix not in language_by_suffix:
            continue
        category = classify_path(path)
        lines = safe_line_count(path)
        if lines is None:
            continue
        language = language_by_suffix[suffix]
        totals["files"] += 1
        totals["lines"] += lines
        by_category[category]["files"] += 1
        by_category[category]["lines"] += lines
        by_language[language]["files"] += 1
        by_language[language]["lines"] += lines
        item: dict[str, Any] = {
            "path": rel(path),
            "category": category,
            "language": language,
            "lines": lines,
        }
        if suffix == ".py":
            ast_metrics = python_ast_metrics(path)
            item["ast"] = ast_metrics
            ast_totals.update(ast_metrics)
        file_metrics.append(item)

    route_pattern = re.compile(r"@router\.(get|post|put|patch|delete)\(")
    frontend_route_pattern = re.compile(r"\bpath\s*:\s*['\"]")
    api_route_count = 0
    frontend_route_count = 0
    for item in file_metrics:
        path = ROOT / item["path"]
        if item["path"].startswith("backend/app/api/routes/"):
            api_route_count += len(route_pattern.findall(read_text(path)))
        if item["path"] == "frontend/src/router/index.ts":
            frontend_route_count += len(frontend_route_pattern.findall(read_text(path)))

    return {
        "generated_at": utc_now(),
        "summary": {
            **dict(totals),
            "backend_api_route_decorators": api_route_count,
            "frontend_route_entries": frontend_route_count,
            "python_ast": dict(ast_totals),
        },
        "by_category": {key: dict(value) for key, value in sorted(by_category.items())},
        "by_language": {key: dict(value) for key, value in sorted(by_language.items())},
        "largest_files": sorted(file_metrics, key=lambda item: item["lines"], reverse=True)[:100],
        "files": file_metrics,
    }


def configured_environment_names() -> list[dict[str, Any]]:
    env_path = ROOT / "backend" / ".env"
    if not env_path.exists():
        return []
    results: list[dict[str, Any]] = []
    # Reading only variable names and the empty/non-empty state is allowed by Task 25A.
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
            results.append({"name": name.strip(), "configured": bool(value.strip())})
    return sorted(results, key=lambda item: item["name"])


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def project_dependency_inventory(files: list[Path]) -> dict[str, Any]:
    pyproject = load_toml(ROOT / "backend" / "pyproject.toml")
    project = pyproject.get("project", {})
    direct_python = project.get("dependencies", [])
    locked_python: list[str] = []
    uv_lock_path = ROOT / "backend" / "uv.lock"
    if uv_lock_path.exists():
        try:
            uv_lock = load_toml(uv_lock_path)
            locked_python = sorted(
                {
                    str(package.get("name"))
                    for package in uv_lock.get("package", [])
                    if isinstance(package, dict) and package.get("name")
                }
            )
        except (OSError, tomllib.TOMLDecodeError):
            locked_python = []

    package_json = json.loads(read_text(ROOT / "frontend" / "package.json"))
    package_lock_path = ROOT / "frontend" / "package-lock.json"
    locked_npm_count = 0
    if package_lock_path.exists():
        package_lock = json.loads(read_text(package_lock_path))
        locked_npm_count = len(package_lock.get("packages", {}))

    lower_locked = {name.lower() for name in locked_python}
    native_risks = [
        {"dependency": name, "risk": risk}
        for name, risk in NATIVE_DEPENDENCY_HINTS.items()
        if name in lower_locked or any(name in item.lower() for item in direct_python)
    ]

    windows_matches: list[dict[str, Any]] = []
    patterns = {
        "windows_absolute_path": re.compile(r"[A-Za-z]:\\"),
        "powershell_or_exe": re.compile(r"(?i)\b(?:powershell(?:\.exe)?|[A-Za-z0-9_.-]+\.exe)\b"),
        "windows_service": re.compile(r"(?i)\b(?:Get-Service|Start-Service|sc\.exe)\b"),
    }
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES or is_private_runtime_path(path):
            continue
        if classify_path(path) in {"historical_delivery_file", "static_build_artifact"}:
            continue
        text = read_text(path)
        for kind, pattern in patterns.items():
            count = len(pattern.findall(text))
            if count:
                windows_matches.append({"path": rel(path), "indicator": kind, "count": count})

    return {
        "generated_at": utc_now(),
        "python": {
            "requires_python": project.get("requires-python"),
            "direct_dependencies": direct_python,
            "locked_package_count": len(locked_python),
            "locked_packages": locked_python,
            "native_or_system_dependency_risks": native_risks,
        },
        "frontend": {
            "scripts": package_json.get("scripts", {}),
            "dependencies": package_json.get("dependencies", {}),
            "dev_dependencies": package_json.get("devDependencies", {}),
            "locked_package_entries": locked_npm_count,
        },
        "platform_coupling": {
            "windows_specific_occurrences": windows_matches,
            "powershell_script_count": sum(1 for path in files if path.suffix.lower() == ".ps1"),
            "shell_script_count": sum(1 for path in files if path.suffix.lower() == ".sh"),
            "real_machine_acceptance": "not_executed",
        },
        "environment_configuration": {
            "policy": "names and configured booleans only; values are intentionally omitted",
            "items": configured_environment_names(),
        },
    }


def source_files(files: Iterable[Path]) -> list[Path]:
    return [
        path
        for path in files
        if path.suffix.lower() in SOURCE_SUFFIXES
        and classify_path(path)
        not in {"historical_delivery_file", "static_build_artifact", "possible_deprecated_file"}
    ]


def all_source_text(files: Iterable[Path]) -> dict[str, str]:
    return {rel(path): read_text(path) for path in source_files(files)}


def candidate(
    path: str,
    evidence: list[str],
    classification: str,
    confidence: str,
    risk: str,
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "candidate": path,
        "evidence": evidence,
        "classification": classification,
        "confidence": confidence,
        "risk": risk,
        "recommended_action": recommended_action,
    }


def dead_code_candidates(files: list[Path]) -> list[dict[str, Any]]:
    texts = all_source_text(files)
    results: list[dict[str, Any]] = []

    frontend_targets = [
        path
        for path in files
        if rel(path).startswith(("frontend/src/components/", "frontend/src/api/", "frontend/src/views/"))
        and path.suffix.lower() in {".vue", ".ts"}
    ]
    combined_frontend = "\n".join(
        text for name, text in texts.items() if name.startswith("frontend/src/")
    )
    for path in frontend_targets:
        relative = rel(path)
        stem = path.stem
        references = len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(stem)}(?![A-Za-z0-9_])", combined_frontend))
        if references <= 1:
            classification = "REVIEW_BEFORE_REMOVE"
            if relative.startswith("frontend/src/views/"):
                classification = "UNKNOWN"
            results.append(
                candidate(
                    relative,
                    [f"static name references across frontend/src: {references}", "dynamic routes and aliases require manual review"],
                    classification,
                    "medium" if classification == "REVIEW_BEFORE_REMOVE" else "low",
                    "static analysis can miss dynamic imports, route loading, and string-based references",
                    "confirm router, menu, API call, and browser coverage before any removal task",
                )
            )

    asset_targets = [
        path
        for path in files
        if rel(path).startswith("frontend/src/assets/") and path.is_file()
    ]
    for path in asset_targets:
        relative = rel(path)
        if path.name not in combined_frontend:
            results.append(
                candidate(
                    relative,
                    ["asset filename not referenced by frontend/src text"],
                    "REVIEW_BEFORE_REMOVE",
                    "medium",
                    "CSS/runtime URL construction may not be visible to the filename scan",
                    "verify built bundle and browser rendering before removal",
                )
            )

    python_targets = [
        path
        for path in files
        if rel(path).startswith("backend/app/") and path.suffix.lower() == ".py" and path.name != "__init__.py"
    ]
    combined_python = "\n".join(text for name, text in texts.items() if name.endswith(".py"))
    dynamic_roots = {
        "backend/app/services/agent_tools/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/services/agent_orchestrators/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/services/external_api_adapters/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/services/model_adapters/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/services/vector_store_adapters/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/services/embedding_adapters/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/services/ocr_adapters/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/api/routes/": "KEEP_DYNAMIC_REGISTRATION",
        "backend/app/models/": "KEEP_DYNAMIC_REGISTRATION",
    }
    for path in python_targets:
        relative = rel(path)
        module_name = relative.removesuffix(".py").replace("/", ".").removeprefix("backend.")
        stem = path.stem
        import_hits = combined_python.count(module_name) + len(re.findall(rf"\b{re.escape(stem)}\b", combined_python))
        if import_hits <= 1:
            classification = "REVIEW_BEFORE_REMOVE"
            for prefix, forced in dynamic_roots.items():
                if relative.startswith(prefix):
                    classification = forced
                    break
            results.append(
                candidate(
                    relative,
                    [f"static module/name references across Python sources: {import_hits}"],
                    classification,
                    "low",
                    "registries, __init__ model imports, routers, and reflection can bypass ordinary imports",
                    "inspect runtime registration and existing flow scripts before any removal task",
                )
            )

    return sorted(results, key=lambda item: (item["classification"], item["candidate"]))


def normalized_source_digest(path: Path) -> str:
    text = read_text(path)
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def ast_function_groups(files: list[Path]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for path in files:
        if path.suffix.lower() != ".py" or classify_path(path) == "historical_delivery_file":
            continue
        try:
            tree = ast.parse(read_text(path), filename=rel(path))
        except (SyntaxError, OSError, ValueError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or len(node.body) < 2:
                continue
            body = ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            groups[digest].append(f"{rel(path)}:{node.lineno}:{node.name}")
    return [
        {
            "candidate": "duplicate_function_body",
            "evidence": locations,
            "classification": "REVIEW_BEFORE_REMOVE",
            "confidence": "high",
            "risk": "mechanical consolidation may alter route-specific errors or transaction behavior",
            "recommended_action": "review for a shared helper during a dedicated local-refactor task",
        }
        for locations in groups.values()
        if len(locations) > 1
    ]


def duplicate_code_candidates(files: list[Path]) -> list[dict[str, Any]]:
    digest_groups: dict[str, list[str]] = defaultdict(list)
    for path in source_files(files):
        if path.stat().st_size < 80:
            continue
        digest_groups[normalized_source_digest(path)].append(rel(path))
    exact = [
        {
            "candidate": "exact_normalized_file_duplicate",
            "evidence": paths,
            "classification": "REVIEW_BEFORE_REMOVE",
            "confidence": "high",
            "risk": "platform-specific or compatibility copies may be intentional",
            "recommended_action": "compare callers and platform roles before consolidation",
        }
        for paths in digest_groups.values()
        if len(paths) > 1
    ]
    route_alias = {
        "candidate": "backend/app/api/routes/knowledge.py upload route alias",
        "evidence": ["POST /api/knowledge/upload", "POST /api/knowledge/documents/upload"],
        "classification": "KEEP_COMPATIBILITY",
        "confidence": "high",
        "risk": "removing the legacy alias may break historical clients",
        "recommended_action": "document the canonical route and deprecate only with client telemetry",
    }
    return sorted(exact + ast_function_groups(files) + [route_alias], key=lambda item: str(item["candidate"]))


def count_indicator(path: Path, pattern: re.Pattern[str]) -> int:
    if path.suffix.lower() not in TEXT_SUFFIXES or is_private_runtime_path(path):
        return 0
    return len(pattern.findall(read_text(path)))


def deprecated_code_candidates(files: list[Path]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    known = [
        (ROOT / "frontend_legacy_before_cupProject_20260611_185550", "historical frontend snapshot"),
        (ROOT / "frontend_legacy_file_list_20260611_185550.txt", "historical frontend snapshot manifest"),
        (ROOT / "docs.zip", "historical archive outside the active docs tree"),
    ]
    for path, reason in known:
        if path.exists():
            results.append(
                candidate(
                    rel(path),
                    [reason, "not part of the active backend/frontend source roots"],
                    "REVIEW_BEFORE_REMOVE",
                    "high",
                    "may still be required for historical traceability or manual recovery",
                    "retain during Task 25A; decide archive/removal policy in Task 25H",
                )
            )

    old_port_pattern = re.compile(r"127\.0\.0\.1:(?:8000|5432)|localhost:(?:8000|5432)")
    for path in files:
        count = count_indicator(path, old_port_pattern)
        if not count:
            continue
        category = classify_path(path)
        if category in {"documentation", "local_operations_or_smoke_script", "test_or_audit_script", "local_operations_script"}:
            results.append(
                candidate(
                    rel(path),
                    [f"legacy/default 8000 or 5432 endpoint occurrences: {count}"],
                    "KEEP_COMPATIBILITY" if path.name in {"README.md", "final_smoke_test.ps1"} else "REVIEW_BEFORE_REMOVE",
                    "medium",
                    "can test the wrong local service in the current 8010/55432 environment",
                    "parameterize through BASE_URL/DATABASE_URL and preserve documented defaults only where intentional",
                )
            )
    return sorted(results, key=lambda item: item["candidate"])


def infer_test_types(path: Path) -> list[str]:
    name = path.name.lower()
    kinds: list[str] = []
    if path.suffix.lower() == ".mjs" or "browser" in name or "frontend_route" in name:
        kinds.append("browser_test")
    if "security" in name or "secret" in name or "sanit" in name or "rbac" in name or "upload" in name:
        kinds.append("security_test")
    if "performance" in name or "baseline" in name:
        kinds.append("performance_test")
    if "migration" in name or "alembic" in name:
        kinds.append("migration_test")
    if "real" in name or "online" in name:
        kinds.append("real_provider_test")
    if "smoke" in name or "acceptance" in name or "flow" in name:
        kinds.append("api_or_service_flow_test")
    if not kinds:
        kinds.append("specialized_check_script")
    return sorted(set(kinds))


def infer_modules(name: str) -> list[str]:
    lower = name.lower()
    aliases = {
        "auth": ["auth", "rbac", "security"],
        "device": ["device"],
        "knowledge": ["knowledge", "contribution", "review"],
        "retrieval": ["retrieval", "rag", "dashvector", "vector"],
        "diagnosis": ["diagnosis"],
        "sop": ["sop"],
        "task": ["task", "workorder"],
        "record_center": ["record", "trace"],
        "knowledge_graph": ["knowledge_graph", "kg"],
        "multimodal": ["multimodal", "ocr", "mimo", "media"],
        "agent": ["agent", "conversion"],
        "external_provider": ["external", "cloud", "provider", "model_gateway"],
        "system": ["system", "environment", "postgresql"],
    }
    modules = [module for module, tokens in aliases.items() if any(token in lower for token in tokens)]
    return modules or ["cross_cutting"]


def test_inventory(files: list[Path]) -> dict[str, Any]:
    test_files = [
        path
        for path in files
        if (
            rel(path).startswith("backend/scripts/check_")
            or rel(path).startswith("scripts/")
            or path.suffix.lower() == ".mjs"
            or "test" in path.name.lower()
        )
        and path.suffix.lower() in {".py", ".mjs", ".ps1", ".sh"}
    ]
    items = [
        {
            "path": rel(path),
            "test_types": infer_test_types(path),
            "modules": infer_modules(path.name),
            "lines": safe_line_count(path),
        }
        for path in sorted(set(test_files), key=lambda item: rel(item))
    ]

    modules = [
        "auth",
        "device",
        "knowledge",
        "retrieval",
        "diagnosis",
        "sop",
        "task",
        "record_center",
        "knowledge_graph",
        "multimodal",
        "agent",
        "external_provider",
        "system",
    ]
    dimensions = [
        "unit_test",
        "service_test",
        "api_test",
        "browser_test",
        "performance_test",
        "security_test",
        "real_provider_test",
        "loongarch_test",
    ]
    coverage: dict[str, dict[str, str]] = {}
    for module in modules:
        relevant = [item for item in items if module in item["modules"]]
        text = " ".join(item["path"].lower() + " " + " ".join(item["test_types"]) for item in relevant)
        row = {dimension: "missing" for dimension in dimensions}
        if relevant:
            row["service_test"] = "script_coverage"
            row["api_test"] = "script_coverage" if any("flow" in item["path"] or "smoke" in item["path"] for item in relevant) else "partial"
        for dimension in ["browser_test", "performance_test", "security_test", "real_provider_test"]:
            if dimension in text:
                row[dimension] = "script_coverage"
        row["loongarch_test"] = "static_script_only" if "loongarch" in text else "missing"
        # No tests/ package or pytest dependency is present; do not label flow scripts as unit tests.
        row["unit_test"] = "missing_standard_pytest_suite"
        coverage[module] = row

    return {
        "generated_at": utc_now(),
        "summary": {
            "test_or_check_files": len(items),
            "standard_pytest_suite": False,
            "pytest_declared_dependency": False,
            "browser_test_files": sum("browser_test" in item["test_types"] for item in items),
            "security_test_files": sum("security_test" in item["test_types"] for item in items),
            "real_provider_test_files": sum("real_provider_test" in item["test_types"] for item in items),
        },
        "items": items,
        "coverage_matrix": coverage,
        "interpretation": "Specialized flow/smoke scripts provide valuable integration evidence but are not a standard pytest unit-test system.",
    }


def main() -> int:
    files, privacy = iter_inventory_files()
    outputs = {
        "project_file_inventory.json": project_file_inventory(files, privacy),
        "project_code_inventory.json": project_code_inventory(files),
        "project_dependency_inventory.json": project_dependency_inventory(files),
        "dead_code_candidates.json": {
            "generated_at": utc_now(),
            "policy": "candidates only; Task 25A performs no deletion",
            "items": dead_code_candidates(files),
        },
        "duplicate_code_candidates.json": {
            "generated_at": utc_now(),
            "policy": "candidates only; compatibility and dynamic registration are preserved",
            "items": duplicate_code_candidates(files),
        },
        "deprecated_code_candidates.json": {
            "generated_at": utc_now(),
            "policy": "candidates only; historical files are preserved",
            "items": deprecated_code_candidates(files),
        },
        "test_inventory.json": test_inventory(files),
    }
    for name, payload in outputs.items():
        write_json(name, payload)

    summary = {
        "status": "passed",
        "output_directory": rel(OUTPUT_DIR),
        "outputs": sorted(outputs),
        "files_inventoried": outputs["project_file_inventory.json"]["summary"]["files_inventoried"],
        "code_files": outputs["project_code_inventory.json"]["summary"]["files"],
        "code_lines": outputs["project_code_inventory.json"]["summary"]["lines"],
        "dead_code_candidates": len(outputs["dead_code_candidates.json"]["items"]),
        "duplicate_code_candidates": len(outputs["duplicate_code_candidates.json"]["items"]),
        "deprecated_code_candidates": len(outputs["deprecated_code_candidates.json"]["items"]),
        "test_or_check_files": outputs["test_inventory.json"]["summary"]["test_or_check_files"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
