from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.environ.get("ENERGY_BACKEND_URL", "http://127.0.0.1:8000")
PASSWORD = os.environ.get("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")


def request(method: str, path: str, *, token: str | None = None, payload: dict | None = None, expect_error: bool = False):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            code = parsed.get("code")
            if expect_error:
                if code not in (0, 200):
                    return {"status": code, "body": parsed}
                raise AssertionError(f"Expected error for {method} {path}, got success")
            if code not in (0, 200):
                raise AssertionError(f"{method} {path} returned code={code}: {parsed}")
            return parsed.get("data")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if expect_error and exc.code in (401, 403):
            return {"status": exc.code, "body": body}
        raise AssertionError(f"{method} {path} failed HTTP {exc.code}: {body}") from exc


def login(username: str) -> str:
    data = request("POST", "/api/auth/login", payload={"username": username, "password": PASSWORD})
    token = data.get("access_token")
    if not token:
        raise AssertionError(f"Login did not return token for {username}")
    return token


def query(params: dict) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})


def main() -> int:
    admin_token = login("admin")
    viewer_token = login("viewer")

    overview = request("GET", "/api/kg/overview", token=admin_token)
    print({"step": "overview", "nodes": overview.get("node_count"), "edges": overview.get("edge_count")})

    documents = request(
        "GET",
        "/api/knowledge/documents?" + query({"parse_status": "parsed", "review_status": "approved", "page": 1, "page_size": 1}),
        token=admin_token,
    )
    if not documents.get("items"):
        raise AssertionError("No approved parsed knowledge document is available for KG extraction")
    document_id = documents["items"][0]["id"]

    extraction = request(
        "POST",
        f"/api/kg/extract/from-document/{document_id}",
        token=admin_token,
        payload={"max_chunks": 10},
    )
    candidate_count = extraction["run"]["candidate_count"]
    if candidate_count < 2:
        raise AssertionError(f"Expected multiple graph candidates, got {candidate_count}")
    print({"step": "extract", "document_id": document_id, "candidate_count": candidate_count})

    candidates = request(
        "GET",
        "/api/kg/candidates?" + query({"run_id": extraction["run"]["id"], "status": "pending", "page": 1, "page_size": 100}),
        token=admin_token,
    )["items"]
    node_candidate = next((item for item in candidates if item["candidate_type"] == "node"), None)
    edge_candidate = next((item for item in candidates if item["candidate_type"] == "edge"), None)
    if not node_candidate or not edge_candidate:
        raise AssertionError("Extraction did not produce both node and edge candidates")

    approved_node = request("POST", f"/api/kg/candidates/{node_candidate['id']}/approve?comment=flow-check", token=admin_token)
    approved_edge = request("POST", f"/api/kg/candidates/{edge_candidate['id']}/approve?comment=flow-check", token=admin_token)
    node_id = approved_node.get("approved_node_id")
    edge_id = approved_edge.get("approved_edge_id")
    if not node_id or not edge_id:
        raise AssertionError("Candidate approval did not create node and edge records")
    print({"step": "approve", "node_id": node_id, "edge_id": edge_id})

    nodes = request("GET", "/api/kg/nodes?page=1&page_size=5", token=admin_token)
    edges = request("GET", "/api/kg/edges?page=1&page_size=5", token=admin_token)
    evidence = request("GET", "/api/kg/evidence?page=1&page_size=5", token=admin_token)
    neighborhood = request("GET", f"/api/kg/neighborhood/{node_id}", token=admin_token)
    if not nodes.get("items") or not edges.get("items") or not evidence.get("items"):
        raise AssertionError("Graph nodes, edges, or evidence are not visible after approval")
    if not neighborhood.get("nodes"):
        raise AssertionError("Neighborhood query returned no nodes")

    remaining_pending = [item for item in candidates if item["id"] not in {node_candidate["id"], edge_candidate["id"]}]
    if remaining_pending:
        forbidden = request(
            "POST",
            f"/api/kg/candidates/{remaining_pending[0]['id']}/approve?comment=viewer-should-fail",
            token=viewer_token,
            expect_error=True,
        )
        print({"step": "viewer_forbidden", "status": forbidden["status"]})

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "node_id": node_id,
            "edge_id": edge_id,
            "visible_nodes": nodes["total"],
            "visible_edges": edges["total"],
            "visible_evidence": evidence["total"],
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print({"status": "failed", "error": str(exc)})
        raise SystemExit(1)
