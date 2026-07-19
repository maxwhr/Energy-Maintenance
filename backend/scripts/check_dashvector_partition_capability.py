from __future__ import annotations

import argparse
import json
from uuid import uuid4

from task25b_r2_u2_common import now_iso, write_json

from app.core.config import get_settings
from app.services.vector_store_adapters import DashVectorAdapter, VectorRecord


def adapter(partition: str) -> DashVectorAdapter:
    settings = get_settings()
    return DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
        collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace=partition,
        dimension=settings.DASHVECTOR_DIMENSION, metric=settings.DASHVECTOR_METRIC,
        dtype=settings.DASHVECTOR_DTYPE, timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
        upsert_batch_size=1, allow_real_api=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    allowed = bool(args.allow_real_api and settings.TASK25B_ALLOW_REAL_API and settings.DASHVECTOR_REAL_CALL_ENABLED and settings.DASHVECTOR_ENABLED)
    pilot = settings.DASHVECTOR_PILOT_PARTITION
    payload = {
        "generated_at": now_iso(), "status": "BLOCKED_CONFIG", "existing_cluster": True,
        "collection": settings.DASHVECTOR_PHYSICAL_COLLECTION, "dimension": settings.DASHVECTOR_DIMENSION,
        "metric": settings.DASHVECTOR_METRIC, "dtype": settings.DASHVECTOR_DTYPE,
        "list_partitions": False, "pilot_partition": pilot, "created": False, "described": False,
        "self_match": False, "default_partition_isolated": False, "probe_deleted": False,
        "new_cluster": False, "new_collection": False, "collection_deleted": False, "secret_output": False,
    }
    if not allowed:
        payload["blocked_reason"] = "real API gate is disabled"
        write_json("dashvector_partition_capability.json", payload)
        return 2
    pilot_adapter = adapter(pilot)
    base_adapter = adapter(settings.DASHVECTOR_NAMESPACE or "default")
    probe_id = f"task25br2u2_probe_{uuid4().hex}"
    vector = [0.0] * 1024
    vector[0] = 1.0
    try:
        pilot_adapter.ensure_collection(dimension=1024)
        before = pilot_adapter._request("GET", f"/v1/collections/{settings.DASHVECTOR_PHYSICAL_COLLECTION}/partitions")
        payload["list_partitions"] = True
        before_output = before.get("output") or []
        before_names = before_output if isinstance(before_output, list) else before_output.get("partitions") or []
        existed = pilot in {str(item) for item in before_names}
        pilot_adapter.ensure_partition(pilot)
        payload["created"] = not existed
        after = pilot_adapter._request("GET", f"/v1/collections/{settings.DASHVECTOR_PHYSICAL_COLLECTION}/partitions")
        after_output = after.get("output") or []
        after_names = after_output if isinstance(after_output, list) else after_output.get("partitions") or []
        payload["described"] = pilot in {str(item) for item in after_names}
        record = VectorRecord(
            vector_id=probe_id, vector=vector,
            metadata={"object_type": "task25b_r2_u2_partition_probe", "chunk_id": probe_id, "document_id": probe_id},
        )
        pilot_adapter.upsert_vectors([record])
        hits = pilot_adapter.query_vectors(vector=vector, top_k=3, filters={"object_type": "task25b_r2_u2_partition_probe"})
        payload["self_match"] = bool(hits and hits[0].vector_id == probe_id)
        base_hits = base_adapter.query_vectors(vector=vector, top_k=10, filters={"object_type": "task25b_r2_u2_partition_probe"})
        payload["default_partition_isolated"] = not any(item.vector_id == probe_id for item in base_hits)
        pilot_adapter.delete_vectors([probe_id])
        payload["probe_deleted"] = True
        payload["status"] = "PASSED" if all(payload[key] for key in ("list_partitions", "described", "self_match", "default_partition_isolated", "probe_deleted")) else "FAILED"
    except Exception as exc:
        payload["status"] = "BLOCKED_PARTITION_CAPABILITY"
        payload["blocked_reason"] = str(exc)[:240]
        try:
            pilot_adapter.delete_vectors([probe_id])
            payload["probe_deleted"] = True
        except Exception:
            pass
    write_json("dashvector_partition_capability.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
