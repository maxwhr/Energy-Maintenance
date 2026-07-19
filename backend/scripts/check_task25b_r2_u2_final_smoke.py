from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from task25b_r2_u2_common import ROOT, now_iso, write_json


def request_json(base_url: str, path: str, *, token: str | None = None, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(base_url + path, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8012")
    args = parser.parse_args()
    credentials_path = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))["admin"]
    health_status, health = request_json(args.base_url, "/api/health")
    login_status, login = request_json(args.base_url, "/api/auth/login", payload=credentials)
    token = login.get("data", {}).get("access_token")
    review_status, review = request_json(
        args.base_url,
        "/api/review/knowledge?review_status=pending_review&manufacturer=huawei&page=1&page_size=100",
        token=token,
    )
    pilot_status, pilot = request_json(args.base_url, "/api/retrieval/pilot/status", token=token)
    official = [item for item in review.get("data", {}).get("items", []) if item.get("source_type") == "vendor_official"]
    pilot_data = pilot.get("data", {})
    passed = (
        health_status == 200 and health.get("code") == 200
        and login_status == 200 and bool(token)
        and review_status == 200 and len(official) == 9
        and all(item.get("review_status") == "pending_review" for item in official)
        and all(not (item.get("metadata_json") or {}).get("approved_for_pilot") for item in official)
        and pilot_status == 200
        and pilot_data.get("pilot_collection") == "energy_kn_te_v4_1024_v1"
        and pilot_data.get("pilot_partition") == "pilot_r2"
        and pilot_data.get("collection_isolation_mode") == "partition"
        and pilot_data.get("full_reindex_allowed") is False
    )
    payload = {
        "generated_at": now_iso(), "status": "PASSED" if passed else "FAILED",
        "base_url": args.base_url, "health": health_status, "login": login_status,
        "review_api": review_status, "pending_vendor_documents": len(official),
        "approved_for_pilot": sum(bool((item.get("metadata_json") or {}).get("approved_for_pilot")) for item in official),
        "pilot_status_api": pilot_status,
        "pilot_collection": pilot_data.get("pilot_collection"),
        "pilot_partition": pilot_data.get("pilot_partition"),
        "isolation_mode": pilot_data.get("collection_isolation_mode"),
        "full_reindex_allowed": pilot_data.get("full_reindex_allowed"),
        "credential_values_output": False, "secret_output": False,
    }
    write_json("final_smoke.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
