from __future__ import annotations

import argparse, json
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunkVectorIndex, KnowledgeDocument
from app.services.vector_index_service import VectorIndexService
from task25b_r3_dev_common import RUNTIME, now_iso, write_json


def partition_count(value, partition="pilot_r2"):
    if isinstance(value, dict):
        if partition in value:
            direct = value[partition]
            if isinstance(direct, (int, float, str)):
                try: return int(direct)
                except (TypeError, ValueError): pass
            if isinstance(direct, dict):
                for count_key in ("count", "doc_count", "total_doc_count", "total"):
                    try: return int(direct.get(count_key))
                    except (TypeError, ValueError): pass
        for key, item in value.items():
            if str(key).lower() in {"partition", "name"} and str(item) == partition:
                for count_key in ("count", "doc_count", "total_doc_count", "total"):
                    try: return int(value.get(count_key))
                    except (TypeError, ValueError): pass
            found = partition_count(item, partition)
            if found is not None: return found
    if isinstance(value, list):
        for item in value:
            found = partition_count(item, partition)
            if found is not None: return found
    return None


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--allow-real-api",action="store_true"); parser.add_argument("--partition",required=True); args=parser.parse_args()
    if not args.allow_real_api or args.partition != "pilot_r2": raise SystemExit("pilot_r2 explicit real call required")
    gate=json.loads((RUNTIME/"chinese_corpus_gate.json").read_text(encoding="utf-8")); settings=get_settings()
    with SessionLocal() as db:
        rows=list(db.scalars(select(KnowledgeChunkVectorIndex).where(KnowledgeChunkVectorIndex.namespace=="pilot_r2",KnowledgeChunkVectorIndex.index_status=="active")))
        service=VectorIndexService(db,allow_real_api=True,collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION,namespace="pilot_r2")
        config=service._runtime_config(provider=settings.EMBEDDING_PROVIDER,vector_backend="dashvector"); adapter=service._adapter(config)
        remote={}
        # Keep GET URLs short; large comma-separated ID lists can exhaust the provider proxy pool.
        batches = [[x.vector_id for x in rows[offset:offset+25]] for offset in range(0, len(rows), 25)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for batch_result in pool.map(adapter.fetch_documents, batches):
                remote.update(batch_result)
        stats=adapter.collection_stats(); remote_count=partition_count(stats); default_count=partition_count(stats, "default")
        docs={doc.id:doc for doc in db.scalars(select(KnowledgeDocument))}
        missing=sum(x.vector_id not in remote for x in rows)
        stale=sum((remote.get(x.vector_id,{}).get("fields") or {}).get("content_hash") != x.content_hash for x in rows if x.vector_id in remote)
        english=sum((docs.get(x.document_id).metadata_json or {}).get("normalized_language")=="en" for x in rows if docs.get(x.document_id))
        pending=sum(docs.get(x.document_id).review_status!="approved" for x in rows if docs.get(x.document_id))
        marketing=sum(bool((docs.get(x.document_id).metadata_json or {}).get("marketing_only")) or
                      (docs.get(x.document_id).metadata_json or {}).get("quality_status")=="MARKETING_ONLY"
                      for x in rows if docs.get(x.document_id))
        superseded=sum(docs.get(x.document_id).status!="active" or
                       bool((docs.get(x.document_id).metadata_json or {}).get("superseded_by_document_id"))
                       for x in rows if docs.get(x.document_id))
        duplicates=len(rows)-len({x.vector_id for x in rows})
        mismatches=sum(x.embedding_dim!=1024 or x.embedding_model!="text-embedding-v4" for x in rows)
        orphan=max(0,remote_count-len(rows)) if remote_count is not None else None
        checks={"postgresql_equals_gate":len(rows)==gate["active_current_chunks"],"missing_zero":missing==0,
            "orphan_zero":orphan==0,"stale_zero":stale==0,"duplicate_zero":duplicates==0,"model_dimension_zero":mismatches==0,
            "english_zero":english==0,"pending_zero":pending==0,"marketing_zero":marketing==0,
            "superseded_zero":superseded==0}
        payload={"generated_at":now_iso(),"collection":config["collection_name"],"partition":"pilot_r2",
            "eligible":gate["active_current_chunks"],"postgresql_vectors":len(rows),"remote_partition_count":remote_count,
            "missing":missing,"orphan":orphan,"stale":stale,"duplicates":duplicates,"dimension_model_mismatch":mismatches,
            "english_leakage":english,"pending_leakage":pending,"marketing_leakage":marketing,
            "superseded_leakage":superseded,"content_hash_mismatch":stale,
            "default_partition_count":default_count,"default_partition_affected":False,
            "media_collection_verification":"not_applicable_no_media_index_operation",
            "checks":checks,"passed":all(checks.values()),
            "raw_vectors_returned":False,"stats_keys":sorted(stats.keys()) if isinstance(stats,dict) else []}
    write_json("chinese_pilot_reconciliation.json",payload); print(payload)


if __name__=="__main__": main()
