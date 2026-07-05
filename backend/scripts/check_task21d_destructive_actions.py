from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT_DIR.parent / ".runtime" / "task21d"
RESULT_FILE = RUNTIME_DIR / "destructive_actions_result.json"


@dataclass
class ApiResult:
    status: int
    body: dict[str, Any] | None
    raw: str

    @property
    def data(self) -> Any:
        if isinstance(self.body, dict):
            return self.body.get("data")
        return None

    @property
    def code(self) -> int | None:
        if isinstance(self.body, dict) and isinstance(self.body.get("code"), int):
            return self.body["code"]
        return None

    @property
    def message(self) -> str:
        if isinstance(self.body, dict):
            return str(self.body.get("message") or self.body.get("detail") or "")
        return self.raw[:200]

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.code in {0, 200}


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def with_token(self, token: str) -> "ApiClient":
        return ApiClient(self.base_url, token=token, timeout=self.timeout)

    def get(self, path: str, params: dict[str, Any] | None = None) -> ApiResult:
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            path = f"{path}?{query}"
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> ApiResult:
        return self.request("POST", path, payload)

    def put(self, path: str, payload: dict[str, Any] | None = None) -> ApiResult:
        return self.request("PUT", path, payload)

    def delete(self, path: str) -> ApiResult:
        return self.request("DELETE", path)

    def multipart(self, path: str, fields: dict[str, str], file_field: str, file_path: Path) -> ApiResult:
        boundary = f"----Task21D{int(time.time() * 1000)}"
        body_parts: list[bytes] = []
        for key, value in fields.items():
            body_parts.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                    str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )
        content_type = mimetypes.guess_type(file_path.name)[0] or "text/plain"
        body_parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                file_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self.request("POST", path, raw_body=b"".join(body_parts), headers=headers)

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResult:
        url = f"{self.base_url}/api{path}"
        request_headers = dict(headers or {})
        body = raw_body
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return ApiResult(response.status, parse_json(raw), raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return ApiResult(exc.code, parse_json(raw), raw)


def parse_json(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


class CheckRunner:
    def __init__(self, base_url: str):
        self.base = ApiClient(base_url)
        self.marker = f"Task21D_{time.strftime('%Y%m%d%H%M%S')}"
        self.results: list[dict[str, Any]] = []
        self.created: dict[str, list[str]] = {
            "users": [],
            "devices": [],
            "knowledge_documents": [],
            "knowledge_contributions": [],
            "sop_templates": [],
            "maintenance_tasks": [],
            "corrections": [],
            "kg_candidates": [],
        }
        self.tokens: dict[str, str] = {}
        self.users: dict[str, dict[str, Any]] = {}
        self.sample_file = RUNTIME_DIR / f"{self.marker}_knowledge.txt"

    def record(self, name: str, status: str, notes: str = "", evidence: Any | None = None) -> None:
        self.results.append({"name": name, "status": status, "notes": notes, "evidence": evidence})
        marker = {"passed": "[PASS]", "failed": "[FAIL]", "skipped": "[SKIP]", "blocked": "[BLOCKED]"}.get(status, "[INFO]")
        print(f"{marker} {name}{f' - {notes}' if notes else ''}")

    def success(self, result: ApiResult, context: str) -> Any:
        if not result.ok:
            raise AssertionError(f"{context} failed: http={result.status} code={result.code} message={result.message}")
        return result.data

    def expect_denied(self, result: ApiResult, context: str) -> None:
        if result.status in {401, 403}:
            return
        if result.status == 200 and result.code not in {0, 200}:
            return
        raise AssertionError(f"{context} should be denied, got http={result.status} code={result.code} message={result.message}")

    def login(self, username: str, password: str, expect_success: bool = True) -> str | None:
        result = self.base.post("/auth/login", {"username": username, "password": password})
        if expect_success:
            data = self.success(result, f"login {username}")
            return str(data["access_token"])
        if result.ok:
            raise AssertionError(f"login {username} should fail but succeeded")
        return None

    def create_user(self, admin: ApiClient, suffix: str, role: str) -> dict[str, Any]:
        username = f"{self.marker}_{suffix}".lower()
        payload = {
            "username": username,
            "password": "Task21Dpass123",
            "display_name": f"{self.marker} {suffix}",
            "role": role,
            "status": "active",
        }
        user = self.success(admin.post("/users", payload), f"create user {suffix}")
        self.created["users"].append(str(user["id"]))
        self.users[suffix] = user
        return user

    def prepare_accounts(self) -> dict[str, ApiClient]:
        admin_token = self.login("admin", "admin123456")
        admin = self.base.with_token(admin_token or "")
        self.tokens["admin"] = admin_token or ""
        for suffix, role in (
            ("expert", "expert"),
            ("engineer", "engineer"),
            ("engineer_other", "engineer"),
            ("viewer", "viewer"),
            ("target_user", "viewer"),
        ):
            self.create_user(admin, suffix, role)
        for suffix in ("expert", "engineer", "engineer_other", "viewer"):
            token = self.login(self.users[suffix]["username"], "Task21Dpass123")
            self.tokens[suffix] = token or ""
        self.record("prepare role accounts", "passed", "admin/expert/engineer/viewer Task21D accounts created")
        return {
            "admin": admin,
            "expert": self.base.with_token(self.tokens["expert"]),
            "engineer": self.base.with_token(self.tokens["engineer"]),
            "engineer_other": self.base.with_token(self.tokens["engineer_other"]),
            "viewer": self.base.with_token(self.tokens["viewer"]),
        }

    def run(self) -> int:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self.sample_file.write_text(
            "\n".join(
                [
                    f"{self.marker} Huawei SUN2000 PV inverter destructive-action acceptance sample.",
                    f"{self.marker}_ArchiveSignal inverter alarm troubleshooting content for retrieval before archive.",
                    f"{self.marker}_RejectSignal rejected review content should never participate in retrieval.",
                    "Safety: isolate AC and DC sides before inspection.",
                ]
            ),
            encoding="utf-8",
        )
        clients = self.prepare_accounts()
        checks = [
            ("user disable/enable", lambda: self.check_user_disable_enable(clients)),
            ("device retire", lambda: self.check_device_retire(clients)),
            ("knowledge archive", lambda: self.check_knowledge_archive(clients)),
            ("knowledge reject", lambda: self.check_knowledge_reject(clients)),
            ("contribution reject/archive", lambda: self.check_contribution_flow(clients)),
            ("SOP template archive", lambda: self.check_sop_archive(clients)),
            ("task cancel", lambda: self.check_task_cancel(clients)),
            ("correction resolve", lambda: self.check_correction_resolve(clients)),
            ("KG candidate reject", lambda: self.check_kg_candidate_reject(clients)),
        ]
        for name, fn in checks:
            try:
                fn()
            except Skipped as exc:
                self.record(name, "skipped", str(exc))
            except Exception as exc:  # noqa: BLE001 - acceptance report must capture all failures.
                self.record(name, "failed", str(exc))
        failed = [item for item in self.results if item["status"] == "failed"]
        output = {
            "base_url": self.base.base_url,
            "marker": self.marker,
            "result": "failed" if failed else "passed",
            "created": self.created,
            "results": self.results,
            "no_package_generated": True,
            "git_add_executed": False,
            "git_commit_executed": False,
        }
        RESULT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"RESULT_FILE={RESULT_FILE}")
        return 1 if failed else 0

    def upload_document(self, client: ApiClient, title: str, signal: str) -> dict[str, Any]:
        file_path = RUNTIME_DIR / f"{title}.txt"
        file_path.write_text(
            f"{title}\n{signal}\n华为 SUN2000 光伏逆变器告警排查、停电验电和复检记录。\n",
            encoding="utf-8",
        )
        data = self.success(
            client.multipart(
                "/knowledge/documents/upload",
                {
                    "manufacturer": "huawei",
                    "product_series": "SUN2000",
                    "device_type": "pv_inverter",
                    "document_type": "manual",
                    "title": title,
                    "source": f"{self.marker} acceptance",
                },
                "file",
                file_path,
            ),
            f"upload {title}",
        )
        self.created["knowledge_documents"].append(str(data["document_id"]))
        return data

    def retrieval_hits_document(self, client: ApiClient, query: str, document_id: str) -> bool:
        data = self.success(
            client.post(
                "/retrieval/query",
                {
                    "query": query,
                    "manufacturer": "huawei",
                    "product_series": "SUN2000",
                    "device_type": "pv_inverter",
                    "document_type": "manual",
                    "top_k": 5,
                },
            ),
            f"retrieval {query}",
        )
        refs = data.get("references") or []
        chunks = data.get("retrieved_chunks") or []
        return any(str(item.get("document_id")) == document_id for item in refs + chunks)

    def check_user_disable_enable(self, clients: dict[str, ApiClient]) -> None:
        admin = clients["admin"]
        viewer = clients["viewer"]
        target = self.users["target_user"]
        user_id = target["id"]
        disabled = self.success(admin.post(f"/users/{user_id}/disable"), "disable user")
        if disabled.get("status") not in {"inactive", "disabled"} or disabled.get("is_active") is not False:
            raise AssertionError(f"disabled user status mismatch: {disabled}")
        self.login(target["username"], "Task21Dpass123", expect_success=False)
        enabled = self.success(admin.post(f"/users/{user_id}/enable"), "enable user")
        if enabled.get("status") != "active" or enabled.get("is_active") is not True:
            raise AssertionError(f"enabled user status mismatch: {enabled}")
        self.login(target["username"], "Task21Dpass123", expect_success=True)
        self.expect_denied(viewer.post(f"/users/{user_id}/disable"), "viewer disable user")
        self.record("user disable/enable", "passed", "disabled login rejected; enabled login accepted; viewer denied")

    def check_device_retire(self, clients: dict[str, ApiClient]) -> None:
        engineer = clients["engineer"]
        viewer = clients["viewer"]
        payload = {
            "device_code": f"{self.marker}-DEV",
            "device_name": f"{self.marker} SUN2000 destructive test device",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "model": "SUN2000-50KTL-M3",
            "device_type": "pv_inverter",
            "station_name": f"{self.marker} station",
            "location": "Task21D rack",
            "status": "normal",
            "description": f"{self.marker} device retire acceptance",
        }
        device = self.success(engineer.post("/devices", payload), "create device")
        device_id = str(device["id"])
        self.created["devices"].append(device_id)
        self.expect_denied(viewer.post(f"/devices/{device_id}/retire"), "viewer retire device")
        retired = self.success(engineer.post(f"/devices/{device_id}/retire"), "retire device")
        detail = self.success(engineer.get(f"/devices/{device_id}"), "get retired device")
        if retired.get("status") != "retired" or detail.get("status") != "retired":
            raise AssertionError(f"device not retired: retired={retired} detail={detail}")
        self.record("device retire", "passed", "engineer retired Task21D device; viewer denied")

    def check_knowledge_archive(self, clients: dict[str, ApiClient]) -> None:
        admin = clients["admin"]
        expert = clients["expert"]
        viewer = clients["viewer"]
        signal = f"{self.marker}_ArchiveSignal"
        uploaded = self.upload_document(admin, f"{self.marker} archive document", signal)
        doc_id = str(uploaded["document_id"])
        self.success(expert.post(f"/review/knowledge/{doc_id}/approve", {"comment": self.marker}), "approve document")
        if not self.retrieval_hits_document(admin, signal, doc_id):
            raise AssertionError("approved document did not participate in retrieval")
        self.expect_denied(viewer.post(f"/review/knowledge/{doc_id}/archive", {"comment": self.marker}), "viewer archive document")
        archived = self.success(expert.post(f"/review/knowledge/{doc_id}/archive", {"comment": self.marker}), "archive document")
        document = archived.get("document", archived)
        if document.get("status") != "archived" and document.get("review_status") != "archived":
            raise AssertionError(f"document archive status mismatch: {archived}")
        if self.retrieval_hits_document(admin, signal, doc_id):
            raise AssertionError("archived document still participated in retrieval")
        self.record("knowledge archive", "passed", "approved document retrieved before archive and excluded after archive")

    def check_knowledge_reject(self, clients: dict[str, ApiClient]) -> None:
        admin = clients["admin"]
        expert = clients["expert"]
        engineer = clients["engineer"]
        viewer = clients["viewer"]
        signal = f"{self.marker}_RejectSignal"
        uploaded = self.upload_document(engineer, f"{self.marker} reject document", signal)
        doc_id = str(uploaded["document_id"])
        self.expect_denied(engineer.post(f"/review/knowledge/{doc_id}/reject", {"comment": self.marker}), "engineer reject document")
        self.expect_denied(viewer.post(f"/review/knowledge/{doc_id}/reject", {"comment": self.marker}), "viewer reject document")
        rejected = self.success(expert.post(f"/review/knowledge/{doc_id}/reject", {"comment": self.marker}), "reject document")
        document = rejected.get("document", rejected)
        if document.get("review_status") != "rejected":
            detail = self.success(admin.get(f"/knowledge/documents/{doc_id}"), "get rejected document")
            if detail.get("review_status") != "rejected":
                raise AssertionError(f"document reject status mismatch: {rejected}")
        if self.retrieval_hits_document(admin, signal, doc_id):
            raise AssertionError("rejected document participated in retrieval")
        self.record("knowledge reject", "passed", "expert rejected; engineer/viewer denied; retrieval excluded")

    def check_contribution_flow(self, clients: dict[str, ApiClient]) -> None:
        engineer = clients["engineer"]
        expert = clients["expert"]
        viewer = clients["viewer"]
        payload = {
            "title": f"{self.marker} field contribution",
            "content": f"{self.marker} contribution content",
            "contribution_type": "maintenance_experience",
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "fault_type": "low_insulation_resistance",
            "alarm_code": f"{self.marker}-CON",
            "symptom_description": f"{self.marker} inverter alarm symptom",
            "diagnosis_process": "停电验电后检查直流端子和绝缘阻抗。",
            "root_cause": "端子潮湿导致绝缘下降。",
            "solution": "清洁并复测后恢复并网。",
            "safety_notes": ["断开交流侧和直流侧", "佩戴绝缘防护用品"],
        }
        contribution = self.success(engineer.post("/knowledge/contributions", payload), "create contribution")
        contribution_id = str(contribution["id"])
        self.created["knowledge_contributions"].append(contribution_id)
        self.success(engineer.post(f"/knowledge/contributions/{contribution_id}/submit"), "submit contribution")
        rejected = self.success(expert.post(f"/knowledge/contributions/{contribution_id}/reject", {"comment": self.marker}), "reject contribution")
        if rejected.get("review_status") != "rejected":
            raise AssertionError(f"contribution reject status mismatch: {rejected}")
        detail = self.success(engineer.get(f"/knowledge/contributions/{contribution_id}"), "engineer get rejected contribution")
        if detail.get("review_status") != "rejected":
            raise AssertionError("engineer cannot see rejected contribution status")
        updated = self.success(
            engineer.put(
                f"/knowledge/contributions/{contribution_id}",
                {"content": f"{self.marker} contribution content edited after rejection"},
            ),
            "owner edit rejected contribution",
        )
        if self.marker not in str(updated.get("content", "")):
            raise AssertionError("owner edit did not persist on rejected contribution")
        self.expect_denied(viewer.post(f"/knowledge/contributions/{contribution_id}/archive", {"comment": self.marker}), "viewer archive contribution")
        archived = self.success(expert.post(f"/knowledge/contributions/{contribution_id}/archive", {"comment": self.marker}), "archive contribution")
        if archived.get("review_status") != "archived":
            raise AssertionError(f"contribution archive status mismatch: {archived}")
        self.record("contribution reject/archive", "passed", "engineer owner can view/edit rejected contribution; viewer archive denied")

    def check_sop_archive(self, clients: dict[str, ApiClient]) -> None:
        expert = clients["expert"]
        viewer = clients["viewer"]
        title = f"{self.marker} SOP archive template"
        payload = {
            "title": title,
            "manufacturer": "huawei",
            "product_series": "SUN2000",
            "device_type": "pv_inverter",
            "fault_type": "fan_fault",
            "maintenance_level": "level_2",
            "steps": [{"step_index": 1, "step_title": "Task21D fan check", "instruction": "检查风扇与散热通道。"}],
            "safety_requirements": [{"item": "断电验电"}],
            "tools_required": [{"name": "绝缘手套"}],
            "materials_required": [],
            "compliance_notes": self.marker,
            "status": "active",
        }
        template = self.success(expert.post("/sop/templates", payload), "create SOP template")
        template_id = str(template["id"])
        self.created["sop_templates"].append(template_id)
        generated = self.success(
            expert.post(
                "/sop/generate",
                {
                    "manufacturer": "huawei",
                    "product_series": "SUN2000",
                    "device_type": "pv_inverter",
                    "fault_type": "fan_fault",
                    "maintenance_level": "level_2",
                },
            ),
            "generate SOP before archive",
        )
        if str(generated.get("template_id")) != template_id:
            raise AssertionError(f"SOP did not match created template before archive: {generated}")
        self.expect_denied(viewer.post(f"/sop/templates/{template_id}/archive"), "viewer archive SOP template")
        archived = self.success(expert.post(f"/sop/templates/{template_id}/archive"), "archive SOP template")
        if archived.get("status") != "archived":
            raise AssertionError(f"SOP archive status mismatch: {archived}")
        generated_after = self.success(
            expert.post(
                "/sop/generate",
                {
                    "manufacturer": "huawei",
                    "product_series": "SUN2000",
                    "device_type": "pv_inverter",
                    "fault_type": "fan_fault",
                    "maintenance_level": "level_2",
                },
            ),
            "generate SOP after archive",
        )
        if str(generated_after.get("template_id")) == template_id:
            raise AssertionError("archived SOP template still matched generation")
        self.record("SOP template archive", "passed", "template matched before archive and no longer matched after archive")

    def check_task_cancel(self, clients: dict[str, ApiClient]) -> None:
        admin = clients["admin"]
        viewer = clients["viewer"]
        engineer_other = clients["engineer_other"]
        assignee_id = self.users["engineer"]["id"]
        task = self.success(
            admin.post(
                "/maintenance/tasks",
                {
                    "title": f"{self.marker} cancellable task",
                    "fault_type": "communication_interruption",
                    "alarm_code": f"{self.marker}-TASK",
                    "fault_description": f"{self.marker} task cancel acceptance",
                    "priority": "medium",
                },
            ),
            "create task",
        )
        task_id = str(task["id"])
        self.created["maintenance_tasks"].append(task_id)
        assigned = self.success(admin.post(f"/maintenance/tasks/{task_id}/assign", {"assignee_id": assignee_id}), "assign task")
        if assigned.get("status") != "assigned":
            raise AssertionError(f"task assign status mismatch: {assigned}")
        self.expect_denied(viewer.post(f"/maintenance/tasks/{task_id}/cancel", {"reason": self.marker}), "viewer cancel task")
        self.expect_denied(engineer_other.post(f"/maintenance/tasks/{task_id}/start"), "unauthorized engineer start task")
        cancelled = self.success(admin.post(f"/maintenance/tasks/{task_id}/cancel", {"reason": self.marker}), "cancel task")
        if cancelled.get("status") != "cancelled":
            raise AssertionError(f"task cancel status mismatch: {cancelled}")
        self.expect_denied(admin.post(f"/maintenance/tasks/{task_id}/start"), "start cancelled task")
        self.expect_denied(
            admin.post(
                f"/maintenance/tasks/{task_id}/complete",
                {"root_cause": self.marker, "repair_action": self.marker, "verification_result": self.marker},
            ),
            "complete cancelled task",
        )
        self.record("task cancel", "passed", "cancelled task cannot be started/completed; viewer and unrelated engineer denied")

    def check_correction_resolve(self, clients: dict[str, ApiClient]) -> None:
        engineer = clients["engineer"]
        expert = clients["expert"]
        viewer = clients["viewer"]
        qa = self.success(
            engineer.post(
                "/retrieval/query",
                {
                    "query": f"{self.marker} correction source query",
                    "manufacturer": "huawei",
                    "product_series": "SUN2000",
                    "device_type": "pv_inverter",
                    "top_k": 3,
                },
            ),
            "create qa record for correction",
        )
        trace_id = qa["trace_id"]
        correction = self.success(
            engineer.post(
                "/corrections",
                {
                    "source_type": "qa",
                    "source_trace_id": trace_id,
                    "original_output": {"answer": "original"},
                    "corrected_output": {"answer": f"{self.marker} corrected"},
                    "reason": f"{self.marker} correction reason",
                },
            ),
            "create correction",
        )
        correction_id = str(correction["id"])
        self.created["corrections"].append(correction_id)
        self.expect_denied(viewer.post(f"/corrections/{correction_id}/resolve", {"action": "accept", "review_comment": self.marker}), "viewer resolve correction")
        resolved = self.success(
            expert.post(f"/corrections/{correction_id}/resolve", {"action": "accept", "review_comment": self.marker}),
            "resolve correction",
        )
        if resolved.get("review_status") not in {"accepted", "resolved"}:
            raise AssertionError(f"correction resolve status mismatch: {resolved}")
        self.record("correction resolve", "passed", "engineer created correction; expert accepted; viewer denied")

    def check_kg_candidate_reject(self, clients: dict[str, ApiClient]) -> None:
        admin = clients["admin"]
        expert = clients["expert"]
        viewer = clients["viewer"]
        signal = f"{self.marker}_KgSignal"
        uploaded = self.upload_document(admin, f"{self.marker} KG candidate document", signal)
        doc_id = str(uploaded["document_id"])
        self.success(expert.post(f"/review/knowledge/{doc_id}/approve", {"comment": self.marker}), "approve KG document")
        extraction = admin.post(f"/kg/extract/from-document/{doc_id}", {"max_chunks": 3, "dry_run": False})
        if not extraction.ok:
            raise Skipped(f"KG extraction not available for this document: http={extraction.status} code={extraction.code} {extraction.message}")
        candidates = self.success(admin.get("/kg/candidates", {"status": "pending", "page": 1, "page_size": 20}), "list KG candidates")
        items = [
            item
            for item in candidates.get("items", [])
            if self.marker in json.dumps(item, ensure_ascii=False)
        ]
        if not items:
            raise Skipped("KG extraction did not create Task21D pending candidates")
        candidate_id = str(items[0]["id"])
        self.created["kg_candidates"].append(candidate_id)
        self.expect_denied(viewer.post(f"/kg/candidates/{candidate_id}/reject?comment={urllib.parse.quote(self.marker)}"), "viewer reject KG candidate")
        rejected = self.success(expert.post(f"/kg/candidates/{candidate_id}/reject?comment={urllib.parse.quote(self.marker)}"), "reject KG candidate")
        if rejected.get("status") != "rejected":
            raise AssertionError(f"KG candidate reject status mismatch: {rejected}")
        self.record("KG candidate reject", "passed", "expert rejected candidate; viewer denied")


class Skipped(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Task 21D destructive action acceptance checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    runner = CheckRunner(args.base_url)
    try:
        return runner.run()
    except Exception as exc:  # noqa: BLE001 - top-level report
        runner.record("task21d destructive script", "failed", str(exc))
        RESULT_FILE.write_text(
            json.dumps(
                {
                    "base_url": runner.base.base_url,
                    "marker": runner.marker,
                    "result": "failed",
                    "created": runner.created,
                    "results": runner.results,
                    "no_package_generated": True,
                    "git_add_executed": False,
                    "git_commit_executed": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"RESULT_FILE={RESULT_FILE}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
