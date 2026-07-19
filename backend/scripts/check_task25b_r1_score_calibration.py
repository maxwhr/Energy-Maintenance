from __future__ import annotations

import argparse
import hashlib
import statistics

from sqlalchemy import select

from task25b_r1_common import now_iso, write_json
from task25b_r1_eval_common import CANARY_NAMESPACE
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.vector_index_service import VectorIndexService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise RuntimeError("--allow-real-api is required")
    settings = get_settings()
    with SessionLocal() as db:
        row = db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeDocument.title.startswith("Task25BR1_Controlled_Document_"),
            KnowledgeChunk.metadata_json["hard_negative"].as_boolean() == False,  # noqa: E712
        ).order_by(KnowledgeDocument.title, KnowledgeChunk.chunk_index)).first()
        if not row:
            raise RuntimeError("controlled anchor chunk is missing")
        chunk, document = row
        model = document.model or "SUN2000"
        code = ((chunk.metadata_json or {}).get("fault_codes") or ["2064"])[0]
        anchors = {
            "self_match": chunk.content,
            "high_similarity": f"{model} 告警 {code} 维护证据与安全排查步骤",
            "medium_similarity": "光伏逆变器出现告警后如何安全检查直流侧",
            "unrelated": "摩托车发动机机油更换与轮胎保养",
        }
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION,
            namespace=CANARY_NAMESPACE,
        )
        results = {}
        for name, query in anchors.items():
            hits, diagnostics = service.search(query, top_k=10, filters={"device_type": "pv_inverter"})
            results[name] = {
                "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                "hit_count": len(hits),
                "top_normalized_score": hits[0].score if hits else 0.0,
                "top_raw_score": hits[0].raw_score if hits else None,
                "embedding_cache_hit": diagnostics.get("query_embedding_cache_hit", False),
                "embedding_latency_ms": diagnostics.get("query_embedding_latency_ms", 0.0),
                "dashvector_latency_ms": diagnostics.get("dashvector_latency_ms", 0.0),
            }
    relevant = [results[name]["top_normalized_score"] for name in ("self_match", "high_similarity", "medium_similarity")]
    unrelated = results["unrelated"]["top_normalized_score"]
    proposed = max(0.55, min(0.90, (min(relevant) + unrelated) / 2))
    payload = {
        "status": "PASSED", "generated_at": now_iso(), "score_direction": "normalized_higher_is_better",
        "raw_cosine_distance_direction": "lower_is_better", "anchors": results,
        "relevant_score_min": round(min(relevant), 6), "unrelated_score": round(unrelated, 6),
        "proposed_similarity_threshold": round(proposed, 6),
        "raw_vectors_returned": False, "test_v2_labels_read": False,
    }
    write_json("score_calibration.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
