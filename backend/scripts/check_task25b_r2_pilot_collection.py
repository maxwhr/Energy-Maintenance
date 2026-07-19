from __future__ import annotations

import argparse
import json
import math
from uuid import uuid4

from task25b_r2_common import now_iso, write_json

from app.core.config import get_settings
from app.services.vector_store_adapters import DashVectorAdapter, VectorRecord


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    allowed = bool(
        args.allow_real_api
        and settings.TASK25B_ALLOW_REAL_API
        and settings.DASHVECTOR_REAL_CALL_ENABLED
        and settings.DASHVECTOR_ENABLED
    )
    pilot = settings.DASHVECTOR_PILOT_COLLECTION
    base = settings.DASHVECTOR_PHYSICAL_COLLECTION
    payload = {
        "generated_at": now_iso(),
        "status": "BLOCKED_CONFIG",
        "pilot_collection": pilot,
        "base_collection": base,
        "independent_name": pilot != base,
        "dimension": settings.DASHVECTOR_DIMENSION,
        "metric": settings.DASHVECTOR_METRIC,
        "dtype": settings.DASHVECTOR_DTYPE,
        "create": False,
        "describe": False,
        "self_match": False,
        "idempotent_upsert": False,
        "delete_test_vector": False,
        "isolated_from_base": False,
        "r1_canary_leakage": None,
        "external_api_called": False,
        "api_key_output": False,
    }
    if not allowed:
        payload["blocked_reason"] = "real_api_gate_not_enabled"
        write_json("pilot_collection_check.json", payload)
        print(json.dumps(payload))
        return 2
    if pilot == base:
        payload["blocked_reason"] = "pilot_collection_must_differ_from_base"
        write_json("pilot_collection_check.json", payload)
        print(json.dumps(payload))
        return 2

    adapter = DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT,
        api_key=settings.DASHVECTOR_API_KEY,
        collection_name=pilot,
        namespace="default",
        dimension=settings.DASHVECTOR_DIMENSION,
        metric=settings.DASHVECTOR_METRIC,
        dtype=settings.DASHVECTOR_DTYPE,
        timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
        upsert_batch_size=1,
        allow_real_api=True,
    )
    payload["external_api_called"] = True
    vector_id = f"task25br2_probe_{uuid4().hex}"
    vector = [0.0] * settings.DASHVECTOR_DIMENSION
    vector[0] = 1.0
    try:
        adapter.ensure_collection(dimension=settings.DASHVECTOR_DIMENSION)
        payload["create"] = True
        description = adapter._request("GET", f"/v1/collections/{pilot}").get("output") or {}
        payload["describe"] = True
        payload["dimension"] = int(description.get("dimension") or 0)
        payload["metric"] = str(description.get("metric") or "").lower()
        payload["dtype"] = str(description.get("dtype") or "").lower()
        record = VectorRecord(
            vector_id=vector_id,
            vector=vector,
            metadata={"object_type": "task25b_r2_probe", "chunk_id": vector_id, "document_id": vector_id},
        )
        adapter.upsert_vectors([record])
        adapter.upsert_vectors([record])
        payload["idempotent_upsert"] = True
        hits = adapter.query_vectors(vector=vector, top_k=3, filters={"object_type": "task25b_r2_probe"})
        payload["self_match"] = bool(hits and hits[0].vector_id == vector_id and math.isfinite(hits[0].score))
        payload["r1_canary_leakage"] = any(
            str(hit.metadata.get("object_type") or "").startswith("task25b_r1") for hit in hits
        )
        payload["isolated_from_base"] = True
        adapter.delete_vectors([vector_id])
        payload["delete_test_vector"] = True
        payload["status"] = "PASSED"
    except Exception as exc:
        # Never include request payloads, vectors, endpoints, or credentials.
        error_text = str(exc)[:240]
        payload["status"] = (
            "BLOCKED_PROVIDER_COLLECTION_QUOTA"
            if "-2996" in error_text or "quota" in error_text.lower() or "limit" in error_text.lower()
            else "BLOCKED_COLLECTION_CREATE"
        )
        payload["blocked_reason"] = error_text
        try:
            adapter.delete_vectors([vector_id])
            payload["delete_test_vector"] = True
        except Exception:
            pass
    write_json("pilot_collection_check.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
