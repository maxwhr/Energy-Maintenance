from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import select

from task25b_r2_u2_common import RUNTIME, now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeDocument, OperationLog
from app.services.knowledge_service import KnowledgeService


DOCUMENT_TYPE_MAP = {
    "USER_MANUAL": "manual", "INSTALLATION_GUIDE": "manual", "QUICK_GUIDE": "manual",
    "MAINTENANCE_GUIDE": "sop", "ALARM_REFERENCE": "alarm_code",
    "TROUBLESHOOTING_GUIDE": "fault_case", "PART_REPLACEMENT_GUIDE": "sop",
    "COMMISSIONING_GUIDE": "sop", "SAFETY_GUIDE": "sop", "COMMUNICATION_GUIDE": "manual",
    "TECHNICAL_DOCUMENT": "manual",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-pending-documents", action="store_true")
    parser.add_argument("--no-auto-approve", action="store_true")
    parser.add_argument("--official-source-only", action="store_true")
    args = parser.parse_args()
    if not (args.create_pending_documents and args.no_auto_approve and args.official_source_only):
        raise SystemExit("all three explicit safety flags are required")
    quality = json.loads((RUNTIME / "huawei_corpus_quality.json").read_text(encoding="utf-8"))
    candidates = [item for item in quality.get("records", []) if item.get("quality_status") == "READY_FOR_DRAFT_IMPORT"]
    created = parsed = skipped = failed = chunks = 0
    rows = []
    with SessionLocal() as db:
        existing_docs = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_type == "vendor_official")))
        existing_keys = {
            ((item.metadata_json or {}).get("file_sha256"), (item.metadata_json or {}).get("source_url")): item
            for item in existing_docs
        }
        service = KnowledgeService(db)
        for item in candidates:
            key = (item.get("file_sha256"), item.get("source_url"))
            if key in existing_keys:
                document = existing_keys[key]
                skipped += 1
                rows.append({"document_id": str(document.id), "status": "SKIPPED_IDEMPOTENT", "chunk_count": document.chunk_count})
                continue
            document = KnowledgeDocument(
                title=(item.get("document_title") or "Huawei official document")[:255],
                manufacturer="huawei",
                product_series="SUN2000" if item.get("product_family") == "SUN2000" else "FusionSolar",
                model=", ".join((item.get("device_models") or [])[:8])[:128] or None,
                device_type="pv_inverter",
                document_type=DOCUMENT_TYPE_MAP.get(item.get("document_type"), "manual"),
                source=item.get("source_url"), source_type="vendor_official",
                file_name=item.get("relative_file_path", "").rsplit("/", 1)[-1],
                file_path=item.get("relative_file_path"), file_size=item.get("file_size"),
                file_ext=item.get("file_type"), page_count=item.get("page_count"),
                parse_status="processing", parser_name=None, chunk_count=0,
                summary="Huawei vendor-public technical document; redistribution is not authorized by this metadata.",
                metadata_json={
                    "source_provenance": "VENDOR_OFFICIAL", "issuer": "Huawei Technologies Co., Ltd.",
                    "rights_basis": "vendor_public", "source_url": item.get("source_url"),
                    "source_page_url": item.get("source_page_url"), "final_url": item.get("final_url"),
                    "downloaded_at": item.get("downloaded_at"), "file_sha256": item.get("file_sha256"),
                    "document_version": item.get("document_version"), "language": item.get("language"),
                    "product_family": item.get("product_family"), "device_models": item.get("device_models") or [],
                    "vendor_document_type": item.get("document_type"), "release_date": item.get("release_date"),
                    "quality_status": item.get("quality_status"), "vendor_source_verified": True,
                    "content_parse_verified": False, "approved_for_pilot": False,
                    "ocr_required": item.get("ocr_required"), "marketing_only": item.get("marketing_only"),
                    "duplicate": False, "redistribution_authorized": False,
                },
                parsed_at=None, review_status="pending_review", status="active",
            )
            db.add(document)
            db.flush()
            created += 1
            try:
                result = service._parse_and_replace_chunks(document)
                metadata = dict(document.metadata_json or {})
                metadata.update(
                    content_parse_verified=True,
                    parser_version="structured_parser_v1",
                    chunker_version="semantic_chunker_v1",
                    imported_at=now_iso(),
                )
                document.metadata_json = metadata
                document.review_status = "pending_review"
                db.add(document)
                parsed += 1
                chunks += int(result["chunk_count"])
                status = "PENDING_REVIEW_PARSED"
            except Exception as exc:
                document.parse_status = "failed"
                document.error_message = type(exc).__name__
                document.chunk_count = 0
                metadata = dict(document.metadata_json or {})
                metadata["content_parse_verified"] = False
                document.metadata_json = metadata
                failed += 1
                status = "FAILED"
            db.add(OperationLog(
                module="knowledge", action="vendor_official_import", target_type="knowledge_document",
                target_id=str(document.id), operator="task25b_r2_u2_importer",
                trace_id=f"u2-import-{str(document.id).replace('-', '')[:20]}",
                detail={
                    "source_provenance": "VENDOR_OFFICIAL", "file_sha256": item.get("file_sha256"),
                    "review_status": document.review_status, "parse_status": document.parse_status,
                    "approved_for_pilot": False, "automatic_approval": False,
                },
            ))
            rows.append({"document_id": str(document.id), "status": status, "chunk_count": document.chunk_count})
        db.commit()
    payload = {
        "generated_at": now_iso(), "eligible_files": len(candidates), "pending_documents_created": created,
        "parsed": parsed, "chunks": chunks, "skipped_idempotent": skipped, "failed": failed,
        "automatically_approved": 0, "formal_vectors_created": 0, "formal_kg_nodes_created": 0,
        "review_status": "pending_review", "records": rows,
    }
    write_json("huawei_import_result.json", payload)
    print(json.dumps({key: payload[key] for key in ("eligible_files", "pending_documents_created", "parsed", "chunks", "skipped_idempotent", "failed", "automatically_approved")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
