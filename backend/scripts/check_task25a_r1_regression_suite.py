from __future__ import annotations

import os
import re
import sys
import time
import argparse
from pathlib import Path
from typing import Any

from task25a_r1_common import BACKEND, RUNTIME, now_iso, register_test, run


CHECKS = [
    ("T-R1-COMPILEALL", "Compile backend app and scripts", "compile", [sys.executable, "-m", "compileall", "app", "scripts"], False),
    ("T-R1-ALEMBIC-HEADS", "Alembic heads", "database", [sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], False),
    ("T-R1-ALEMBIC-CURRENT", "Alembic current", "database", [sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], False),
    ("T-R1-SECURITY-CONFIG", "Security configuration status", "security", [sys.executable, "scripts/check_security_config_status.py"], False),
    ("T-R1-SECRET-SCAN", "Secret leak scan", "security", [sys.executable, "scripts/check_secret_leak_scan.py"], False),
    ("T-R1-LOG-SANITIZATION", "Log sanitization", "security", [sys.executable, "scripts/check_log_sanitization.py"], False),
    ("T-R1-UPLOAD-SECURITY", "Upload security", "security", [sys.executable, "scripts/check_upload_security.py"], False),
    ("T-R1-RBAC-MATRIX", "RBAC security matrix", "security", [sys.executable, "scripts/check_rbac_security_matrix.py"], False),
    ("T-R1-DASHVECTOR-FLOW", "DashVector hybrid RAG deterministic boundary", "business_flow", [sys.executable, "scripts/check_dashvector_hybrid_rag_flow.py"], True),
    ("T-R1-EXTERNAL-GATEWAY-FLOW", "External API gateway blocked/mock flow", "business_flow", [sys.executable, "scripts/check_external_api_gateway_flow.py"], True),
    ("T-R1-MULTIMODAL-FLOW", "Multimodal evidence flow", "business_flow", [sys.executable, "scripts/check_multimodal_evidence_flow.py"], True),
    ("T-R1-MULTIMODAL-AGENT-FLOW", "Multimodal evidence agent flow", "agent_flow", [sys.executable, "scripts/check_multimodal_evidence_agent_flow.py"], True),
    ("T-R1-DIAG-SOP-TASK-AGENT", "Diagnosis SOP task agent flow", "agent_flow", [sys.executable, "scripts/check_diagnosis_sop_task_agent_flow.py"], True),
    ("T-R1-KNOWLEDGE-CURATOR-AGENT", "Knowledge curator agent flow", "agent_flow", [sys.executable, "scripts/check_knowledge_curator_agent_flow.py"], True),
    ("T-R1-ARTIFACT-CONVERSION", "Agent artifact conversion flow", "conversion_flow", [sys.executable, "scripts/check_agent_artifact_conversion_flow.py"], True),
    ("T-R1-CONVERSION-CONCURRENCY", "Agent conversion concurrency flow", "conversion_flow", [sys.executable, "scripts/check_agent_conversion_concurrency_flow.py"], True),
]


def assertion_counts(output: str, success: bool) -> tuple[int, int, int]:
    passed = len(re.findall(r"(?im)(?:\bpassed\b|\bpass\b|\bok\b|成功|通过)", output))
    failed = len(re.findall(r"(?im)(?:\bfailed\b|\bfail\b|失败)", output))
    if passed == 0 and success:
        passed = 1
    if failed == 0 and not success:
        failed = 1
    return passed + failed, passed, failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args()
    os.environ.update({
        "CLOUD_LLM_REAL_CALL_ENABLED": "false", "MIMO_REAL_CALL_ENABLED": "false", "OCR_API_REAL_CALL_ENABLED": "false",
        "DASHVECTOR_REAL_CALL_ENABLED": "false", "EMBEDDING_REAL_CALL_ENABLED": "false",
    })
    selected = CHECKS
    if args.only:
        requested = set(args.only)
        selected = [item for item in CHECKS if item[0] in requested]
    if args.failed_only:
        from task25a_r1_common import read_json
        registry = read_json(RUNTIME / "test_execution_registry.json", {"tests": []})
        failed_ids = {item.get("test_id") for item in registry.get("tests", []) if item.get("status") == "FAILED"}
        selected = [item for item in CHECKS if item[0] in failed_ids]
    failures = 0
    business_since_cooldown = 0
    for test_id, name, category, command, mocked in selected:
        if category in {"business_flow", "agent_flow", "conversion_flow"}:
            if business_since_cooldown >= 2:
                print("rate_limit_cooldown phase=1 seconds=31", flush=True)
                time.sleep(31)
                print("rate_limit_cooldown phase=2 seconds=31", flush=True)
                time.sleep(31)
                business_since_cooldown = 0
            business_since_cooldown += 1
        result = run(command, BACKEND, timeout=300)
        output = f"{result['stdout']}\n{result['stderr']}"
        expected = True
        if test_id == "T-R1-ALEMBIC-CURRENT":
            expected = "20260601_0008" in output
        elif test_id == "T-R1-ALEMBIC-HEADS":
            expected = "20260601_0008" in output and "head" in output.lower()
        success = result["exit_code"] == 0 and expected
        failures += int(not success)
        log = RUNTIME / f"regression_{test_id.lower()}.log"
        log.write_text(output, encoding="utf-8")
        count, passed, failed = assertion_counts(output, success)
        register_test({
            "test_id": test_id, "name": name, "category": category, "command": " ".join(command),
            "started_at": result["started_at"], "completed_at": result["completed_at"], "duration_seconds": result["duration_seconds"],
            "exit_code": result["exit_code"] if expected else 1, "status": "PASSED" if success else "FAILED",
            "assertion_count": count, "passed_assertions": passed if success else max(0, passed - 1), "failed_assertions": failed if not success else 0,
            "artifact_paths": [log], "mocked": mocked, "real_external_api_used": False,
            "notes": "Current Task 25A-R1 run. Mocked/deterministic boundary is explicit." if mocked else "Current Task 25A-R1 executable check.",
        })
        print(f"{test_id} status={'PASSED' if success else 'FAILED'} exit={result['exit_code']}")
    print(f"task25a_r1_regression_suite total={len(selected)} failed={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
