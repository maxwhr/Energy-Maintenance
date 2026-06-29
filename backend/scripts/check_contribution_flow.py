from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_PASSWORD = os.environ.get("FULL_SMOKE_ADMIN_PASSWORD") or "admin123456"


@dataclass
class ApiResult:
    name: str
    passed: bool
    notes: str = ""


class ContributionFlowClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
        return json.loads(payload)

    def login(self, username: str, password: str) -> str:
        payload = self.request("POST", "/api/auth/login", body={"username": username, "password": password})
        token = ((payload.get("data") or {}).get("access_token") or "").strip()
        if not token:
            raise RuntimeError(f"login failed for {username}: {payload}")
        return token


def ok(payload: dict[str, Any]) -> bool:
    return payload.get("code") in {0, 200}


def data(payload: dict[str, Any]) -> Any:
    return payload.get("data")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Energy-Maintenance knowledge contribution closed-loop smoke check.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()

    client = ContributionFlowClient(args.base_url)
    results: list[ApiResult] = []

    try:
        admin_token = client.login("admin", args.password)
        expert_token = client.login("expert", args.password)
        engineer_token = client.login("engineer", args.password)
        viewer_token = client.login("viewer", args.password)
        results.append(ApiResult("login admin/expert/engineer/viewer", True))

        devices_payload = client.request("GET", "/api/devices?page=1&page_size=10&device_type=pv_inverter", token=engineer_token)
        require(ok(devices_payload), f"device list failed: {devices_payload}")
        devices = data(devices_payload).get("items", [])
        device = devices[0] if devices else {}
        results.append(ApiResult("device dropdown source", True, f"devices={len(devices)}"))

        marker = f"Task18B_Flow_{int(time.time())}"
        base_payload = {
            "title": marker,
            "contribution_type": "maintenance_experience",
            "manufacturer": device.get("manufacturer") or "huawei",
            "product_series": device.get("product_series") or "SUN2000",
            "device_type": "pv_inverter",
            "device_id": device.get("id"),
            "fault_type": "low_insulation_resistance",
            "alarm_code": "LOW-INS",
            "symptom_description": "Huawei SUN2000 inverter reported low insulation resistance after rain.",
            "diagnosis_process": "Isolated DC switches, measured PV string insulation, and checked connectors.",
            "root_cause": "Moist connector and string insulation degradation were found during the field check.",
            "solution": "Replace or dry abnormal connector, retest insulation, and archive the measurement record.",
            "tools_used": ["Insulation resistance tester", "Multimeter"],
            "parts_used": ["PV connector kit"],
            "safety_notes": ["Confirm DC and AC isolation", "Wear electrical PPE"],
            "media_ids": [],
        }

        created = client.request("POST", "/api/knowledge/contributions", token=engineer_token, body=base_payload)
        require(ok(created), f"create contribution failed: {created}")
        contribution = data(created)
        contribution_id = contribution["id"]
        require(contribution["review_status"] == "draft", f"unexpected create status: {contribution}")
        results.append(ApiResult("engineer creates draft contribution", True, contribution_id))

        submitted = client.request("POST", f"/api/knowledge/contributions/{contribution_id}/submit", token=engineer_token, body={})
        require(ok(submitted) and data(submitted)["review_status"] == "submitted", f"submit failed: {submitted}")
        results.append(ApiResult("engineer submits contribution", True))

        changes = client.request(
            "POST",
            f"/api/knowledge/contributions/{contribution_id}/request-changes",
            token=expert_token,
            body={"comment": "Please add the retest step."},
        )
        require(ok(changes) and data(changes)["review_status"] == "changes_requested", f"request changes failed: {changes}")
        results.append(ApiResult("expert requests changes", True))

        updated_payload = {**base_payload, "solution": base_payload["solution"] + " Confirm recovery after restart."}
        updated = client.request("PUT", f"/api/knowledge/contributions/{contribution_id}", token=engineer_token, body=updated_payload)
        require(ok(updated), f"update after changes failed: {updated}")
        resubmitted = client.request("POST", f"/api/knowledge/contributions/{contribution_id}/submit", token=engineer_token, body={})
        require(ok(resubmitted) and data(resubmitted)["review_status"] == "submitted", f"resubmit failed: {resubmitted}")
        results.append(ApiResult("engineer updates and resubmits", True))

        approved = client.request(
            "POST",
            f"/api/knowledge/contributions/{contribution_id}/approve",
            token=expert_token,
            body={"comment": "Approved for knowledge base conversion."},
        )
        require(ok(approved) and data(approved)["review_status"] == "approved", f"approve failed: {approved}")
        results.append(ApiResult("expert approves contribution", True))

        converted = client.request(
            "POST",
            f"/api/knowledge/contributions/{contribution_id}/convert-to-document",
            token=expert_token,
            body={"comment": "Converted by Task18B smoke flow."},
        )
        require(ok(converted), f"convert failed: {converted}")
        converted_data = data(converted)
        document_id = converted_data["document"]["id"]
        require(converted_data["chunk_count"] > 0, f"converted chunk_count invalid: {converted_data}")
        results.append(ApiResult("expert converts approved contribution", True, f"document_id={document_id}"))

        chunks = client.request("GET", f"/api/knowledge/documents/{document_id}/chunks?page=1&page_size=10", token=admin_token)
        require(ok(chunks) and data(chunks).get("items"), f"converted chunks missing: {chunks}")
        results.append(ApiResult("converted document has chunks", True, f"chunks={data(chunks).get('total')}"))

        retrieval = client.request(
            "POST",
            "/api/retrieval/query",
            token=engineer_token,
            body={
                "query": "SUN2000 low insulation resistance connector field check Task18B",
                "manufacturer": base_payload["manufacturer"],
                "product_series": base_payload["product_series"],
                "device_type": "pv_inverter",
                "top_k": 5,
                "enable_model_enhancement": False,
            },
        )
        retrieved_chunks = (data(retrieval) or {}).get("retrieved_chunks") or []
        references = (data(retrieval) or {}).get("references") or []
        require(ok(retrieval) and retrieved_chunks and references, f"retrieval did not hit contribution chunks: {retrieval}")
        results.append(ApiResult("retrieval finds converted contribution chunks", True, f"references={len(references)}"))

        record_search = client.request(
            "GET",
            f"/api/record-center/search?record_type=knowledge_contribution&keyword={marker}",
            token=admin_token,
        )
        require(ok(record_search) and data(record_search).get("items"), f"record center contribution search failed: {record_search}")
        results.append(ApiResult("record center traces contribution", True))

        reject_marker = f"{marker}_Reject"
        reject_created = client.request(
            "POST",
            "/api/knowledge/contributions",
            token=engineer_token,
            body={**base_payload, "title": reject_marker},
        )
        require(ok(reject_created), f"reject flow create failed: {reject_created}")
        reject_id = data(reject_created)["id"]
        reject_submit = client.request("POST", f"/api/knowledge/contributions/{reject_id}/submit", token=engineer_token, body={})
        require(ok(reject_submit), f"reject flow submit failed: {reject_submit}")
        rejected = client.request(
            "POST",
            f"/api/knowledge/contributions/{reject_id}/reject",
            token=expert_token,
            body={"comment": "Rejected by Task18B smoke flow."},
        )
        require(ok(rejected) and data(rejected)["review_status"] == "rejected", f"reject failed: {rejected}")
        results.append(ApiResult("expert rejects submitted contribution", True, reject_id))

        viewer_create = client.request(
            "POST",
            "/api/knowledge/contributions",
            token=viewer_token,
            body={**base_payload, "title": f"{marker}_ViewerForbidden"},
        )
        require(not ok(viewer_create), f"viewer create unexpectedly succeeded: {viewer_create}")
        viewer_list = client.request("GET", "/api/knowledge/contributions?page=1&page_size=5", token=viewer_token)
        require(ok(viewer_list), f"viewer readonly list failed: {viewer_list}")
        results.append(ApiResult("viewer readonly permission", True))

    except Exception as exc:
        results.append(ApiResult("contribution flow", False, str(exc)))

    summary = {
        "status": "passed" if all(item.passed for item in results) else "failed",
        "base_url": args.base_url,
        "results": [item.__dict__ for item in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
