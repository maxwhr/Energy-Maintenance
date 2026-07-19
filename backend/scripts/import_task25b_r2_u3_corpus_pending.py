from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select

from task25b_r2_u3_common import RUNTIME, now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, OperationLog
from app.services.document_parser import ParsedDocument, ParsedPage
from app.services.semantic_chunker import SemanticChunker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-auto-approve", action="store_true")
    args = parser.parse_args()
    if not args.no_auto_approve:
        raise SystemExit("--no-auto-approve is required")
    internal = json.loads((RUNTIME / "huawei_support_html_internal.json").read_text(encoding="utf-8"))
    quality = json.loads((RUNTIME / "u3_corpus_quality.json").read_text(encoding="utf-8"))
    ready_hashes = {item["content_hash"] for item in quality.get("records", []) if item.get("quality_status") == "READY_FOR_HUMAN_REVIEW"}
    candidates = [item for item in internal.get("records", []) if item.get("content_hash") in ready_hashes]
    created = skipped = chunks_created = failed = metadata_updated = 0
    records = []
    chunker = SemanticChunker(chunk_size=700, overlap=80)
    with SessionLocal() as db:
        existing = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_type == "vendor_official_html")))
        existing_keys = {
            ((item.metadata_json or {}).get("content_hash"), (item.metadata_json or {}).get("source_url")): item
            for item in existing
        }
        for item in candidates:
            key = (item["content_hash"], item["source_url"])
            desired_document_type = item.get("document_type") or "FAQ_TROUBLESHOOTING"
            if key in existing_keys:
                existing_document = existing_keys[key]
                corrected = False
                if existing_document.review_status == "pending_review" and existing_document.document_type != desired_document_type:
                    existing_document.document_type = desired_document_type
                    existing_metadata = dict(existing_document.metadata_json or {})
                    existing_metadata["vendor_document_type"] = desired_document_type
                    existing_document.metadata_json = existing_metadata
                    for existing_chunk in db.scalars(
                        select(KnowledgeChunk).where(KnowledgeChunk.document_id == existing_document.id)
                    ):
                        existing_chunk.document_type = desired_document_type
                    db.add(OperationLog(
                        module="knowledge", action="vendor_official_html_metadata_correction",
                        target_type="knowledge_document", target_id=str(existing_document.id),
                        operator="task25b_r2_u3_importer",
                        trace_id=f"u3-meta-{str(existing_document.id).replace('-', '')[:20]}",
                        detail={"document_type": desired_document_type, "review_status": "pending_review"},
                    ))
                    metadata_updated += 1
                    corrected = True
                skipped += 1
                records.append({
                    "document_id": str(existing_document.id),
                    "status": "METADATA_CORRECTED" if corrected else "SKIPPED_IDEMPOTENT",
                    "document_type": desired_document_type,
                })
                continue
            categories = item.get("equipment_categories") or ["other"]
            document = KnowledgeDocument(
                title=f"{item['product_family']} FAQ - {item['question_title']}"[:255],
                manufacturer="huawei",
                product_series="SUN2000" if item["product_family"] == "SUN2000" else "FusionSolar",
                model=", ".join((item.get("device_models") or [])[:8])[:128] or None,
                device_type="pv_inverter",
                document_type=desired_document_type,
                source=item["source_url"], source_type="vendor_official_html",
                file_name=None, file_path=None, file_size=None, file_ext="html",
                page_count=None, parse_status="processing", parser_name="official_html_structured_v1",
                chunk_count=0, summary="Huawei official support FAQ; vendor_public does not authorize redistribution.",
                metadata_json={
                    "source_provenance": "VENDOR_OFFICIAL", "official_source": True,
                    "issuer": item["issuer"], "rights_basis": "vendor_public",
                    "source_url": item["source_url"], "source_page_url": item["source_page_url"],
                    "page_title": item["page_title"], "question_title": item["question_title"],
                    "page_content_hash": item["page_content_hash"], "content_hash": item["content_hash"],
                    "product_family": item["product_family"], "device_models": item.get("device_models") or [],
                    "equipment_categories": categories, "vendor_document_type": desired_document_type,
                    "language": item["language"], "section_locator": item["section_locator"],
                    "alarm_knowledge": item["alarm_knowledge"], "quality_status": "READY_FOR_HUMAN_REVIEW",
                    "vendor_source_verified": True, "content_parse_verified": True,
                    "approved_for_pilot": False, "marketing_only": False, "duplicate": False,
                    "ocr_required": False, "redistribution_authorized": False,
                    "legacy_device_type_compatibility": True, "collected_at": item["collected_at"],
                },
                parsed_at=None, review_status="pending_review", status="active",
            )
            try:
                db.add(document)
                db.flush()
                markdown = f"# {item['question_title']}\n\n{item['content']}"
                parsed = ParsedDocument(text=markdown, pages=[ParsedPage(page_number=None, text=markdown)], metadata={"parser": "official_html_structured_v1"})
                chunks = chunker.split(parsed)
                if not chunks:
                    raise ValueError("no chunks")
                for chunk in chunks:
                    metadata = dict(chunk.metadata or {})
                    metadata.update(
                        source_locator=item["section_locator"], equipment_categories=categories,
                        alarm_knowledge=item["alarm_knowledge"], source_provenance="VENDOR_OFFICIAL",
                    )
                    db.add(KnowledgeChunk(
                        document_id=document.id, manufacturer="huawei", product_series=document.product_series,
                        device_type=document.device_type, document_type=document.document_type,
                        chunk_index=chunk.chunk_index, content=chunk.content,
                        content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                        section_title=chunk.section_title or item["question_title"], char_count=len(chunk.content),
                        page_number=None, embedding_status="pending", metadata_json=metadata, status="active",
                    ))
                document.parse_status = "parsed"
                document.chunk_count = len(chunks)
                document.parsed_at = datetime.now(timezone.utc)
                db.add(OperationLog(
                    module="knowledge", action="vendor_official_html_import", target_type="knowledge_document",
                    target_id=str(document.id), operator="task25b_r2_u3_importer",
                    trace_id=f"u3-html-{str(document.id).replace('-', '')[:20]}",
                    detail={"review_status": "pending_review", "approved_for_pilot": False, "automatic_approval": False, "content_hash": item["content_hash"]},
                ))
                created += 1
                chunks_created += len(chunks)
                records.append({"document_id": str(document.id), "status": "PENDING_REVIEW", "chunks": len(chunks)})
            except Exception as exc:
                db.rollback()
                failed += 1
                records.append({"status": "FAILED", "error_type": type(exc).__name__, "content_hash": item["content_hash"]})
        db.commit()
    payload = {
        "generated_at": now_iso(), "eligible": len(candidates), "created_pending": created,
        "skipped_idempotent": skipped, "metadata_updated": metadata_updated,
        "failed": failed, "chunks_created": chunks_created,
        "automatically_approved": 0, "formal_vectors_created": 0, "formal_kg_nodes_created": 0,
        "records": records,
    }
    write_json("u3_import_result.json", payload)
    print(json.dumps({k: payload[k] for k in ("eligible", "created_pending", "skipped_idempotent", "failed", "chunks_created", "automatically_approved")}, ensure_ascii=False))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
