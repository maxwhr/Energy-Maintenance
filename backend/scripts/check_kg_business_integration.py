from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


BASE_URL = os.environ.get("ENERGY_BACKEND_URL", "http://127.0.0.1:8000")
PASSWORD = os.environ.get("FULL_SMOKE_ADMIN_PASSWORD", "admin123456")


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    expect_error: bool = False,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            parsed = json.loads(response.read().decode("utf-8") or "{}")
            code = parsed.get("code")
            if expect_error:
                if code not in (0, 200):
                    return parsed
                raise AssertionError(f"Expected business error for {method} {path}, got success")
            if code not in (0, 200):
                raise AssertionError(f"{method} {path} returned code={code}: {parsed}")
            return parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if expect_error and exc.code in (401, 403):
            return {"code": exc.code, "message": body, "data": None}
        raise AssertionError(f"{method} {path} failed HTTP {exc.code}: {body}") from exc


def login(username: str) -> str:
    response = request("POST", "/api/auth/login", payload={"username": username, "password": PASSWORD})
    token = (response.get("data") or {}).get("access_token")
    if not token:
        raise AssertionError(f"Login did not return token for {username}")
    return str(token)


def query(params: dict[str, Any]) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})


def data(response: dict[str, Any]) -> dict[str, Any]:
    value = response.get("data")
    if not isinstance(value, dict):
        raise AssertionError(f"Response data is not an object: {response}")
    return value


def assert_kg_context(value: dict[str, Any], label: str) -> None:
    context = value.get("kg_context")
    if not isinstance(context, dict):
        raise AssertionError(f"{label} did not return kg_context")
    summary = context.get("summary") or {}
    if "matched_node_count" not in summary:
        raise AssertionError(f"{label} kg_context summary is missing matched_node_count")
    if not isinstance(value.get("kg_evidence", context.get("evidence", [])), list):
        raise AssertionError(f"{label} did not return kg evidence list")


def main() -> int:
    admin_token = login("admin")
    viewer_token = login("viewer")

    overview = data(request("GET", "/api/kg/overview", token=admin_token))
    print({"step": "overview", "nodes": overview.get("node_count"), "edges": overview.get("edge_count")})

    graph = data(
        request(
            "GET",
            "/api/kg/graph?" + query({"manufacturer": "huawei", "product_series": "SUN2000", "limit": 30}),
            token=admin_token,
        )
    )
    if "nodes" not in graph or "edges" not in graph:
        raise AssertionError("/api/kg/graph did not return nodes and edges")
    print({"step": "graph", "nodes": len(graph.get("nodes") or []), "edges": len(graph.get("edges") or [])})

    business_context = data(
        request(
            "GET",
            "/api/kg/business-context?"
            + query(
                {
                    "manufacturer": "huawei",
                    "product_series": "SUN2000",
                    "fault_type": "low_insulation_resistance",
                    "question": "SUN2000 绝缘阻抗低告警如何排查",
                }
            ),
            token=admin_token,
        )
    )
    if "matched_nodes" not in business_context or "summary" not in business_context:
        raise AssertionError("/api/kg/business-context returned an invalid payload")
    print(
        {
            "step": "business_context",
            "matched_nodes": len(business_context.get("matched_nodes") or []),
            "evidence": len(business_context.get("evidence") or []),
        }
    )

    retrieval = data(
        request(
            "POST",
            "/api/retrieval/query",
            token=admin_token,
            payload={
                "query": "SUN2000 绝缘阻抗低告警如何排查",
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
                "top_k": 3,
                "enable_kg_enhancement": True,
                "enable_model_enhancement": False,
            },
        )
    )
    assert_kg_context(retrieval, "retrieval")

    diagnosis = data(
        request(
            "POST",
            "/api/diagnosis/analyze",
            token=admin_token,
            payload={
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
                "fault_description": "SUN2000 出现绝缘阻抗低告警，雨后并网失败。",
                "observed_symptoms": ["雨后告警", "并网失败"],
                "enable_kg_enhancement": True,
                "enable_model_enhancement": False,
            },
        )
    )
    assert_kg_context(diagnosis, "diagnosis")

    sop = data(
        request(
            "POST",
            "/api/sop/generate",
            token=admin_token,
            payload={
                "manufacturer": "huawei",
                "product_series": "SUN2000",
                "device_type": "pv_inverter",
                "fault_type": "low_insulation_resistance",
                "maintenance_level": "level_2",
                "enable_kg_enhancement": True,
                "enable_model_enhancement": False,
            },
        )
    )
    assert_kg_context(sop, "sop")

    viewer_graph = data(request("GET", "/api/kg/graph?limit=5", token=viewer_token))
    if "nodes" not in viewer_graph:
        raise AssertionError("viewer could not read graph")
    forbidden = request(
        "POST",
        "/api/kg/nodes",
        token=viewer_token,
        payload={
            "node_type": "fault",
            "canonical_name": "viewer_forbidden_probe",
            "display_name": "viewer forbidden probe",
            "device_type": "pv_inverter",
        },
        expect_error=True,
    )
    print({"step": "viewer_readonly", "business_code": forbidden.get("code")})

    print(
        {
            "status": "passed",
            "retrieval_trace_id": retrieval.get("trace_id"),
            "diagnosis_trace_id": diagnosis.get("trace_id"),
            "sop_title": sop.get("title"),
            "business_context_matched": len(business_context.get("matched_nodes") or []),
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print({"status": "failed", "error": str(exc)})
        raise SystemExit(1)
