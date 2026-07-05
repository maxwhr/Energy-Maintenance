from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.security_config import is_configured_secret  # noqa: E402


SECRET_KEYS = {
    "SECRET_KEY",
    "ADMIN_PASSWORD",
    "DASHVECTOR_API_KEY",
    "EMBEDDING_API_KEY",
    "CLOUD_LLM_API_KEY",
    "CLOUD_VISION_API_KEY",
    "MIMO_API_KEY",
    "OCR_API_KEY",
    "LOCAL_LLM_API_KEY",
    "RERANK_API_KEY",
    "PRIVATE_KEY",
}
PLACEHOLDER_PREFIXES = ("<FILL_", "your_", "replace_", "example", "changeme", "change-", "dummy")
SAMPLE_VALUES = {
    "admin123456",
    "Task18I_pass123",
    "Task24D_pass123",
    "energy_password",
    "energy-maintenance-local-dev-secret-change-me",
    "change-this-secret-in-production",
}
NON_SECRET_KEY_PARTS = {
    "MAX_TOKENS",
    "PROMPT_TOKENS",
    "COMPLETION_TOKENS",
    "TOTAL_TOKENS",
    "TOKEN_USAGE",
    "TOKEN_TYPE",
    "TOKENS",
    "PASSWORD_ITERATIONS",
    "PASSWORD_LENGTH",
    "PASSWORD_HASH",
    "CONFIGURED_PASSWORD",
    "DEFAULT_PASSWORD",
    "VIEWER_PASSWORD",
    "OLDPASSWORD",
    "WEAK_ADMIN_PASSWORDS",
    "API_KEY_CONFIGURED",
    "REQUIRES_API_KEY",
    "API_KEY_ENV_KEY",
    "API_KEY_EXPOSURE",
    "SECRET_KEY_LENGTH",
    "SECRET_KEY_PATTERN",
    "SECRET_ASSIGNMENT_PATTERN",
    "SECURITY_MIN_SECRET_KEY_LENGTH",
    "NON_SECRET_KEY_PARTS",
    "ACCESS_TOKEN_EXPIRE",
    "SECRET_TYPE",
    "SECRET_KEYS",
}
CODE_IDENTIFIER_VALUES = {
    "token",
    "admin_token",
    "engineer_token",
    "expert_token",
    "viewer_token",
    "access_token",
    "password",
    "configured_password",
    "default_password",
    "viewer_password",
    "oldpassword",
    "provider.api_key_env_key",
    "settings.secret_key",
}
TEXT_EXTENSIONS = {
    ".py",
    ".ps1",
    ".ts",
    ".tsx",
    ".js",
    ".vue",
    ".md",
    ".txt",
    ".json",
    ".ini",
    ".toml",
    ".yaml",
    ".yml",
    ".env",
    ".example",
}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "delivery",
    "delivery_staging",
    ".runtime",
    "__pycache__",
}
EXCLUDED_PREFIXES = {
    Path("backend/static/frontend/assets"),
}

SK_PATTERN = re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9._-]{12,}")
BEARER_PATTERN = re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{12,})", re.IGNORECASE)
ASSIGNMENT_PATTERN = re.compile(
    r"\b([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY)[A-Z0-9_]*)\s*[:=]\s*([^\s#\"']+)",
    re.IGNORECASE,
)


def mask_value(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}****{value[-4:]}"


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def is_placeholder(value: str) -> bool:
    stripped = value.strip().strip('"').strip("'")
    lowered = stripped.lower()
    if not stripped:
        return True
    if stripped in SAMPLE_VALUES:
        return True
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    return any(lowered.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES) or "placeholder" in lowered


def is_non_secret_key(key: str) -> bool:
    normalized = key.upper()
    return any(part in normalized for part in NON_SECRET_KEY_PARTS)


def is_allowed_test_marker(value: str, line: str) -> bool:
    lowered = f"{value} {line}".lower()
    return any(
        marker in lowered
        for marker in (
            "task24d-secret-should-not-appear",
            "task24d.token.should.not.appear",
            "should-not-appear",
            "should_not_appear",
            "should_not_be_logged",
            "fake",
            "example",
            "placeholder",
        )
    )


def is_probable_secret_literal(key: str, value: str, line: str) -> bool:
    stripped = value.strip().strip('"').strip("'")
    lowered = stripped.lower()
    if not stripped or is_placeholder(stripped) or is_allowed_test_marker(stripped, line):
        return False
    lowered_line = line.lower()
    if lowered_line.lstrip().startswith("def "):
        return False
    if any(
        marker in lowered_line
        for marker in ("os.getenv", "getenv", "field(", "mapped_column", "hash_password", "verify_password", "==", "!=", '"password": password')
    ):
        return False
    if "(" in stripped or ")" in stripped or stripped.startswith("$"):
        return False
    if lowered in CODE_IDENTIFIER_VALUES:
        return False
    if any(lowered.startswith(f"{identifier}") for identifier in CODE_IDENTIFIER_VALUES):
        return False
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", stripped):
        return False
    if stripped.startswith("sk-") or stripped.lower().startswith("bearer "):
        return True
    if "PASSWORD" in key.upper() or "SECRET" in key.upper() or "PRIVATE_KEY" in key.upper():
        return is_configured_secret(stripped)
    if "API_KEY" in key.upper() or key.upper().endswith("TOKEN"):
        return len(stripped) >= 16 and any(ch.isdigit() for ch in stripped)
    return False


def should_scan(path: Path) -> bool:
    relative = path.relative_to(ROOT_DIR)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if any(part.startswith("frontend_legacy") for part in relative.parts):
        return False
    if any(_is_relative_to(relative, prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    if path.suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".db", ".sqlite"}:
        return False
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {".env", ".env.example", "README.md"}


def _is_relative_to(path: Path, prefix: Path) -> bool:
    try:
        path.relative_to(prefix)
        return True
    except ValueError:
        return False


def add_issue(issues: list[dict], path: Path, line_no: int, secret_type: str, value: str, severity: str) -> None:
    issues.append(
        {
            "file": str(path.relative_to(ROOT_DIR).as_posix()),
            "line": line_no,
            "secret_type": secret_type,
            "masked_preview": mask_value(value),
            "fingerprint": fingerprint(value),
            "severity": severity,
        }
    )


def scan_file(path: Path, issues: list[dict]) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    env_file = path.name == ".env"
    env_example = path.name.endswith(".example") or path.name == ".env.example"
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in SK_PATTERN.finditer(line):
            if not is_allowed_test_marker(match.group(0), line):
                add_issue(issues, path, line_no, "sk_token", match.group(0), "high")
        for match in BEARER_PATTERN.finditer(line):
            token = match.group(1)
            if token.lower().startswith("token") or "{" in token or is_allowed_test_marker(token, line):
                continue
            add_issue(issues, path, line_no, "bearer_token", token, "high")
        for match in ASSIGNMENT_PATTERN.finditer(line):
            key = match.group(1).upper()
            value = match.group(2).strip().strip('"').strip("'")
            if is_non_secret_key(key):
                continue
            if key not in SECRET_KEYS and not any(suffix in key for suffix in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
                continue
            if is_placeholder(value):
                continue
            if env_example:
                if is_probable_secret_literal(key, value, line):
                    add_issue(issues, path, line_no, key, value, "high")
            elif env_file:
                severity = "local_env_note" if is_configured_secret(value) else "info"
                if severity == "local_env_note":
                    add_issue(issues, path, line_no, key, value, severity)
            elif key.endswith("PASSWORD") and value in {"admin123456", "Task18I_pass123", "Task24D_pass123"}:
                add_issue(issues, path, line_no, key, value, "warning")
            elif is_probable_secret_literal(key, value, line):
                add_issue(issues, path, line_no, key, value, "high")
            else:
                continue


def main() -> int:
    settings = get_settings()
    issues: list[dict] = []
    for path in ROOT_DIR.rglob("*"):
        if path.is_file() and should_scan(path):
            scan_file(path, issues)

    blocking = [
        issue
        for issue in issues
        if issue["severity"] == "high" and issue["file"] not in {"backend/.env"}
    ]
    status = "failed" if blocking else ("passed_with_notes" if issues else "passed")
    output = {
        "status": status,
        "scanned_root": str(ROOT_DIR),
        "issues": issues,
        "blocking_count": len(blocking),
        "local_env_contains_configured_secrets": any(issue["severity"] == "local_env_note" for issue in issues),
        "key_values_printed": False,
        "scan_exclude_dirs": settings.security_scan_exclude_dirs,
    }
    runtime_dir = ROOT_DIR / ".runtime" / "security"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "secret_scan_result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "issue_count": len(issues),
                "blocking_count": len(blocking),
                "local_env_contains_configured_secrets": output["local_env_contains_configured_secrets"],
                "key_values_printed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
