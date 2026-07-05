from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.task24c_real_api_common import (  # noqa: E402
    print_result,
    provider_config_summary,
    write_result,
)


SCRIPT_MAP = {
    "dashvector": "check_dashvector_real_optional.py",
    "embedding": "check_dashvector_real_optional.py",
    "cloud_llm": "check_cloud_llm_real_optional.py",
    "mimo": "check_mimo_real_optional.py",
    "ocr": "check_ocr_api_real_optional.py",
}
DEFAULT_PROVIDERS = ["dashvector", "embedding", "cloud_llm", "mimo", "ocr"]


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"status": "failed", "error": "child script did not return JSON"}
    try:
        parsed = json.loads(stdout[start : end + 1])
    except json.JSONDecodeError as exc:
        return {"status": "failed", "error": f"child script returned invalid JSON: {exc}"}
    return parsed if isinstance(parsed, dict) else {"status": "failed", "error": "child JSON is not an object"}


def _run_child(script_name: str, *, allow_real_api: bool, base_url: str | None) -> dict[str, Any]:
    command = [sys.executable, str(SCRIPT_DIR / script_name)]
    if allow_real_api:
        command.append("--allow-real-api")
    if base_url and script_name != "check_dashvector_real_optional.py":
        command.extend(["--base-url", base_url])
    completed = subprocess.run(command, cwd=str(BACKEND_DIR), text=True, capture_output=True, timeout=240)
    result = _extract_json(completed.stdout)
    if completed.returncode != 0 and result.get("status") != "blocked":
        result["status"] = "failed"
        result["returncode"] = completed.returncode
        result["stderr_sanitized_note"] = "Child script stderr was suppressed to avoid leaking local paths or secrets."
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 24C real external API acceptance aggregator.")
    parser.add_argument("--allow-real-api", action="store_true", help="Allow configured provider child scripts to make real calls.")
    parser.add_argument("--providers", default=None, help="Comma-separated provider list: dashvector,embedding,cloud_llm,mimo,ocr.")
    parser.add_argument("--skip-provider", default=None, help="Comma-separated providers to skip.")
    parser.add_argument("--base-url", default=None, help="API base URL, e.g. http://127.0.0.1:8010/api.")
    parser.add_argument("--require-all", action="store_true", help="Treat blocked providers as failures.")
    args = parser.parse_args()

    selected = _parse_csv(args.providers, DEFAULT_PROVIDERS)
    skip = set(_parse_csv(args.skip_provider, []))
    selected = [provider for provider in selected if provider not in skip]
    invalid = [provider for provider in selected if provider not in SCRIPT_MAP]
    if invalid:
        result = {"status": "failed", "invalid_providers": invalid, "valid_providers": sorted(SCRIPT_MAP)}
        write_result("real_external_api_acceptance_result.json", result)
        print_result(result)
        return 1

    if not args.allow_real_api:
        result = {
            "status": "skipped",
            "real_external_api_used": False,
            "reason": "real external API acceptance requires --allow-real-api",
            "selected_providers": selected,
            "skipped_providers": sorted(skip),
            "provider_config": provider_config_summary(),
        }
        write_result("real_external_api_acceptance_result.json", result)
        print_result(result)
        return 0

    executed_scripts: set[str] = set()
    provider_results: dict[str, dict[str, Any]] = {}
    for provider in selected:
        script_name = SCRIPT_MAP[provider]
        if script_name in executed_scripts:
            provider_results[provider] = {
                "status": provider_results.get("dashvector", {}).get("status", "skipped"),
                "shared_script": script_name,
                "shared_with": "dashvector",
            }
            continue
        executed_scripts.add(script_name)
        provider_results[provider] = _run_child(script_name, allow_real_api=True, base_url=args.base_url)

    passed = sum(1 for item in provider_results.values() if item.get("status") == "passed")
    blocked = sum(1 for item in provider_results.values() if item.get("status") == "blocked")
    failed = sum(1 for item in provider_results.values() if item.get("status") == "failed")
    skipped = sum(1 for item in provider_results.values() if item.get("status") == "skipped")
    if args.require_all and blocked:
        failed += blocked
    overall = "failed" if failed else "passed" if passed else "blocked" if blocked else "skipped"
    result = {
        "status": overall,
        "selected_providers": selected,
        "skipped_providers": sorted(skip),
        "summary": {
            "total": len(provider_results),
            "passed": passed,
            "blocked": blocked,
            "failed": failed,
            "skipped": skipped,
            "real_external_api_used": any(bool(item.get("real_external_api_used")) for item in provider_results.values()),
            "require_all": args.require_all,
        },
        "providers": provider_results,
        "provider_config": provider_config_summary(),
    }
    write_result("real_external_api_acceptance_result.json", result)
    print_result(result)
    return 0 if overall in {"passed", "blocked", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
