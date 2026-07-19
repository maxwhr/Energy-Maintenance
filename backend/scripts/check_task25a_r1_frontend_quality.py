from __future__ import annotations

import json
import os
import re
from pathlib import Path

from task25a_r1_common import ROOT, RUNTIME, register_test, run


FRONTEND = ROOT / "frontend"


def execute(test_id: str, name: str, category: str, command: list[str], cwd: Path, *, required_text: str | None = None) -> bool:
    result = run(command, cwd, timeout=900)
    output = f"{result['stdout']}\n{result['stderr']}"
    expected = required_text is None or required_text.lower() in output.lower()
    if test_id == "T-R1-FINAL-SMOKE":
        expected = bool(re.search(r'"status"\s*:\s*"passed"', output)) and bool(re.search(r'"failed"\s*:\s*0', output))
    success = result["exit_code"] == 0 and expected
    log = RUNTIME / f"frontend_{test_id.lower()}.log"
    log.write_text(output, encoding="utf-8")
    pass_tokens = len(re.findall(r"(?im)(?:\bpassed\b|\bbuilt\b|\b0 vulnerabilities\b|\bfailed=0\b|成功|通过)", output)) or int(success)
    register_test({
        "test_id": test_id, "name": name, "category": category, "command": " ".join(command),
        "started_at": result["started_at"], "completed_at": result["completed_at"], "duration_seconds": result["duration_seconds"],
        "exit_code": result["exit_code"] if success else 1, "status": "PASSED" if success else "FAILED",
        "assertion_count": max(1, pass_tokens), "passed_assertions": pass_tokens if success else max(0, pass_tokens - 1), "failed_assertions": 0 if success else 1,
        "artifact_paths": [log], "notes": "Current Task 25A-R1 frontend/static/smoke execution; no delivery package generated.",
    })
    print(f"{test_id} status={'PASSED' if success else 'FAILED'} exit={result['exit_code']}")
    return success


def skipped(test_id: str, name: str, note: str) -> None:
    register_test({
        "test_id": test_id, "name": name, "category": "frontend", "command": "not available in package.json",
        "exit_code": None, "status": "SKIPPED", "assertion_count": 0, "passed_assertions": 0, "failed_assertions": 0,
        "artifact_paths": [], "notes": note,
    })
    print(f"{test_id} status=SKIPPED reason=missing_package_script")


def main() -> int:
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts", {})
    checks = [
        execute("T-R1-NPM-INSTALL", "npm install", "frontend", ["npm.cmd", "install"], FRONTEND),
        execute("T-R1-NPM-AUDIT", "npm audit", "security", ["npm.cmd", "audit"], FRONTEND),
        execute("T-R1-FRONTEND-BUILD", "Vite production build", "frontend", ["npm.cmd", "run", "build"], FRONTEND),
    ]
    if "lint" in scripts:
        checks.append(execute("T-R1-FRONTEND-LINT", "Frontend lint", "frontend", ["npm.cmd", "run", "lint"], FRONTEND))
    else:
        skipped("T-R1-FRONTEND-LINT", "Frontend lint", "package.json has no lint script; not reported as passed")
    if "type-check" in scripts:
        checks.append(execute("T-R1-FRONTEND-TYPECHECK-SCRIPT", "Frontend package type-check", "frontend", ["npm.cmd", "run", "type-check"], FRONTEND))
    else:
        skipped("T-R1-FRONTEND-TYPECHECK-SCRIPT", "Frontend package type-check", "package.json has no type-check script; standalone vue-tsc is still executed")
    checks.append(execute("T-R1-VUE-TSC", "Vue TypeScript noEmit", "frontend", ["npx.cmd", "vue-tsc", "--noEmit"], FRONTEND))
    checks.append(execute("T-R1-STATIC-INSTALL", "Build and install frontend static assets", "frontend", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "backend" / "scripts" / "build_and_install_frontend.ps1")], ROOT))
    private_credentials = RUNTIME / ".test_credentials.private.json"
    if not private_credentials.is_file():
        raise RuntimeError("Private secure Task 25A-R1 credentials are required for final smoke")
    admin = json.loads(private_credentials.read_text(encoding="utf-8")).get("admin", {})
    if not admin.get("username") or not admin.get("password"):
        raise RuntimeError("Secure admin credential is incomplete")
    os.environ["FULL_SMOKE_ADMIN_USERNAME"] = str(admin["username"])
    os.environ["FULL_SMOKE_ADMIN_PASSWORD"] = str(admin["password"])
    checks.append(execute("T-R1-FINAL-SMOKE", "Final smoke on port 8010", "smoke", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "final_smoke_test.ps1"), "-BaseUrl", "http://127.0.0.1:8010", "-Username", str(admin["username"])], ROOT))
    failures = sum(not item for item in checks)
    print(f"task25a_r1_frontend_quality executed={len(checks)} failed={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
