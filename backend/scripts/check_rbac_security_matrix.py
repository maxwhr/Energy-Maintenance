from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_global_acceptance as cga  # noqa: E402


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8010").rstrip("/")
cga.API_BASE_URL = f"{BASE_URL}/api"
cga.APP_BASE_URL = BASE_URL
MARKER = f"Task24D_{time.strftime('%Y%m%d%H%M%S')}"
FAKE_UUID = "00000000-0000-0000-0000-000000000001"


def status_allowed(status: int, response: dict) -> bool:
    code = response.get("code")
    code_text = str(code) if code is not None else ""
    return status not in {401, 403} and not code_text.startswith(("401", "403"))


def status_forbidden(status: int, response: dict) -> bool:
    code = response.get("code")
    code_text = str(code) if code is not None else ""
    return status in {401, 403} or code_text.startswith(("401", "403"))


def add(results: list[dict], name: str, expected: str, status: int, response: dict, passed: bool) -> None:
    results.append(
        {
            "name": name,
            "expected": expected,
            "actual_http": status,
            "actual_code": response.get("code"),
            "passed": passed,
        }
    )
    print(f"[{'passed' if passed else 'failed'}] {name}: expected={expected}, http={status}, code={response.get('code')}")


def request(method: str, path: str, token: str | None = None, payload: dict | None = None) -> tuple[int, dict]:
    return cga.request_json(method, path, token=token, payload=payload, timeout=30)


def expect_allowed(results: list[dict], name: str, method: str, path: str, token: str, payload: dict | None = None) -> None:
    status, response = request(method, path, token, payload)
    add(results, name, "allowed or business validation", status, response, status_allowed(status, response))


def expect_forbidden(results: list[dict], name: str, method: str, path: str, token: str | None, payload: dict | None = None) -> None:
    status, response = request(method, path, token, payload)
    add(results, name, "forbidden", status, response, status_forbidden(status, response))


def multipart_upload(token: str | None, file_name: str) -> tuple[int, dict]:
    body, content_type = cga.multipart_body(
        [
            ("manufacturer", "huawei"),
            ("product_series", "SUN2000"),
            ("device_type", "pv_inverter"),
            ("document_type", "manual"),
            ("title", f"{MARKER} RBAC upload"),
        ],
        "file",
        file_name,
        b"Task24D RBAC upload sample.",
        "text/plain",
    )
    return cga.request_json("POST", "/knowledge/documents/upload", token=token, body=body, content_type=content_type)


def expect_upload_allowed(results: list[dict], name: str, token: str) -> None:
    status, response = multipart_upload(token, f"{MARKER}_allowed.txt")
    add(results, name, "allowed", status, response, status_allowed(status, response))


def expect_upload_forbidden(results: list[dict], name: str, token: str | None) -> None:
    status, response = multipart_upload(token, f"{MARKER}_forbidden.txt")
    add(results, name, "forbidden", status, response, status_forbidden(status, response))


def main() -> int:
    results: list[dict] = []
    admin_token, _ = cga.login(cga.ADMIN_USERNAME, cga.ADMIN_PASSWORD)
    users: dict[str, dict] = {"admin": {"token": admin_token}}
    for role in ("expert", "engineer", "viewer"):
        user = cga.ensure_user(admin_token, f"{MARKER}_{role}", role, f"{MARKER} {role}")
        token, _ = cga.login(user["username"], cga.TEST_PASSWORD)
        users[role] = {"token": token, "id": user["id"]}

    expect_allowed(results, "anonymous health", "GET", "/health", token=None)
    expect_allowed(results, "anonymous system status", "GET", "/system/status", token=None)
    expect_forbidden(results, "anonymous users", "GET", "/users?page=1&page_size=1", token=None)
    expect_forbidden(results, "anonymous vector status", "GET", "/vector-search/status", token=None)

    expect_allowed(results, "admin users list", "GET", "/users?page=1&page_size=1", admin_token)
    expect_forbidden(results, "engineer users list", "GET", "/users?page=1&page_size=1", users["engineer"]["token"])
    expect_forbidden(results, "viewer users list", "GET", "/users?page=1&page_size=1", users["viewer"]["token"])

    expect_upload_allowed(results, "engineer knowledge upload", users["engineer"]["token"])
    expect_upload_forbidden(results, "viewer knowledge upload", users["viewer"]["token"])
    expect_forbidden(
        results,
        "engineer knowledge review approve",
        "POST",
        f"/review/knowledge/{FAKE_UUID}/approve",
        users["engineer"]["token"],
        {"comment": "rbac probe"},
    )
    expect_allowed(
        results,
        "expert knowledge review approve role gate",
        "POST",
        f"/review/knowledge/{FAKE_UUID}/approve",
        users["expert"]["token"],
        {"comment": "rbac probe"},
    )

    contribution_payload = {
        "title": f"{MARKER} contribution",
        "content": "Huawei SUN2000 inverter maintenance experience.",
        "contribution_type": "maintenance_experience",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
    }
    expect_allowed(results, "engineer contribution create", "POST", "/knowledge/contributions", users["engineer"]["token"], contribution_payload)
    expect_forbidden(
        results,
        "engineer contribution approve",
        "POST",
        f"/knowledge/contributions/{FAKE_UUID}/approve",
        users["engineer"]["token"],
        {"comment": "rbac probe"},
    )
    expect_allowed(
        results,
        "expert contribution approve role gate",
        "POST",
        f"/knowledge/contributions/{FAKE_UUID}/approve",
        users["expert"]["token"],
        {"comment": "rbac probe"},
    )

    retrieval_payload = {"query": "SUN2000 insulation alarm inspection", "device_type": "pv_inverter", "top_k": 1}
    expect_allowed(results, "viewer retrieval query", "POST", "/retrieval/query", users["viewer"]["token"], retrieval_payload)
    diagnosis_payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "fault_description": "Task24D insulation alarm probe.",
    }
    expect_allowed(results, "engineer diagnosis analyze", "POST", "/diagnosis/analyze", users["engineer"]["token"], diagnosis_payload)
    expect_forbidden(results, "viewer diagnosis analyze", "POST", "/diagnosis/analyze", users["viewer"]["token"], diagnosis_payload)

    sop_payload = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "maintenance_level": "level_2",
    }
    expect_allowed(results, "engineer sop generate", "POST", "/sop/generate", users["engineer"]["token"], sop_payload)
    expect_forbidden(results, "viewer sop generate", "POST", "/sop/generate", users["viewer"]["token"], sop_payload)

    task_payload = {
        "title": f"{MARKER} RBAC task",
        "fault_type": "low_insulation_resistance",
        "fault_description": "Task24D RBAC task probe",
        "priority": "medium",
    }
    expect_allowed(results, "engineer task create", "POST", "/maintenance/tasks", users["engineer"]["token"], task_payload)
    expect_forbidden(results, "viewer task create", "POST", "/maintenance/tasks", users["viewer"]["token"], task_payload)
    expect_forbidden(
        results,
        "engineer task assign",
        "POST",
        f"/maintenance/tasks/{FAKE_UUID}/assign",
        users["engineer"]["token"],
        {"assignee_id": FAKE_UUID},
    )

    expect_forbidden(results, "viewer OCR trigger", "POST", f"/media/{FAKE_UUID}/ocr", users["viewer"]["token"])
    expect_allowed(results, "viewer OCR status read", "GET", "/media/ocr/status", users["viewer"]["token"])

    job_payload = {"job_type": "multimodal_analysis", "dry_run": True, "mock_run": False}
    expect_allowed(results, "engineer multimodal job create role gate", "POST", f"/multimodal/media/{FAKE_UUID}/jobs", users["engineer"]["token"], job_payload)
    expect_forbidden(results, "viewer multimodal job create", "POST", f"/multimodal/media/{FAKE_UUID}/jobs", users["viewer"]["token"], job_payload)
    expect_forbidden(
        results,
        "engineer multimodal review",
        "POST",
        f"/multimodal/analyses/{FAKE_UUID}/review",
        users["engineer"]["token"],
        {"review_status": "accepted", "review_comment": "rbac probe"},
    )

    dry_run_payload = {"capability": "text_chat", "tool_name": "model_gateway_chat", "input_summary": {"text": "rbac"}}
    expect_allowed(results, "engineer external dry-run", "POST", "/external-apis/dry-run", users["engineer"]["token"], dry_run_payload)
    expect_forbidden(results, "viewer external dry-run", "POST", "/external-apis/dry-run", users["viewer"]["token"], dry_run_payload)
    expect_forbidden(results, "engineer external provider check", "POST", "/external-apis/providers/mimo_2_5/check", users["engineer"]["token"])

    vector_payload = {"vector_backend": "fake_in_memory", "provider": "deterministic_test", "force": True}
    expect_forbidden(results, "engineer vector index", "POST", f"/vector-search/documents/{FAKE_UUID}/index", users["engineer"]["token"], vector_payload)
    expect_forbidden(results, "viewer vector index", "POST", f"/vector-search/documents/{FAKE_UUID}/index", users["viewer"]["token"], vector_payload)
    expect_allowed(results, "expert vector test role gate", "POST", "/vector-search/test-query", users["expert"]["token"], {"text": "SUN2000", "top_k": 1})

    agent_payload = {"agent_code": "knowledge_curator_agent", "input_text": "Task24D RBAC", "dry_run": True}
    expect_allowed(results, "engineer agent run create", "POST", "/agents/runs", users["engineer"]["token"], agent_payload)
    expect_forbidden(results, "viewer agent run create", "POST", "/agents/runs", users["viewer"]["token"], agent_payload)
    expect_forbidden(
        results,
        "engineer agent approval approve",
        "POST",
        f"/agents/approvals/{FAKE_UUID}/approve",
        users["engineer"]["token"],
        {"review_comment": "rbac probe"},
    )
    expect_allowed(
        results,
        "expert agent approval approve role gate",
        "POST",
        f"/agents/approvals/{FAKE_UUID}/approve",
        users["expert"]["token"],
        {"review_comment": "rbac probe"},
    )
    expect_forbidden(
        results,
        "engineer artifact conversion",
        "POST",
        f"/agents/artifacts/{FAKE_UUID}/convert",
        users["engineer"]["token"],
        {"target_type": "knowledge_contribution", "comment": "rbac probe"},
    )

    expect_forbidden(
        results,
        "engineer KG candidate approve",
        "POST",
        f"/kg/candidates/{FAKE_UUID}/approve?comment=rbac",
        users["engineer"]["token"],
    )
    expect_allowed(results, "viewer system status", "GET", "/system/status", users["viewer"]["token"])

    failed = [item for item in results if not item["passed"]]
    output = {"status": "passed" if not failed else "failed", "results": results, "failed": failed}
    runtime_dir = ROOT_DIR / ".runtime" / "security"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "rbac_matrix_result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": output["status"], "checks": len(results), "failed": len(failed)}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
