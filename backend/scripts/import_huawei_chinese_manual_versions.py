from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone

from pypdf import PdfReader
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, OperationLog
from app.services.knowledge_language_policy_service import KnowledgeLanguagePolicyService
from task25b_r3_dev_common import PARSER_VERSION, RUNTIME, normalized, now_iso, write_json


def clean_pages(reader: PdfReader) -> list[str]:
    raw = [(page.extract_text() or "").replace("\x00", "") for page in reader.pages]
    candidates = Counter()
    for text in raw:
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        for line in lines[:3] + lines[-3:]:
            key = normalized(line)
            if 8 <= len(key) <= 100:
                candidates[key] += 1
    repeated = {key for key, count in candidates.items() if count >= max(5, len(raw) // 8)}
    cleaned = []
    for text in raw:
        lines = []
        for line in text.splitlines():
            value = " ".join(line.split())
            if not value or normalized(value) in repeated:
                continue
            if re.search(r"(?:文档版本.*版权所有.*华为.*有限公司|版权所有.*华为.*有限公司.*保留一切权利)|用户手册\s+(?:前言|目录|附录|[0-9])", value):
                continue
            lines.append(value)
        cleaned.append("\n".join(lines))
    return cleaned


def page_chunks(text: str, page_number: int) -> list[tuple[str, str]]:
    if len(text.strip()) < 120:
        return []
    if "版权所有" in text[:180] and ("商标声明" in text or "未经本公司书面许可" in text):
        return []
    toc_signals = len(re.findall(r"\.{4,}\s*\d+$", text, re.M))
    if toc_signals >= 4 or ("目录" in text[:100] and toc_signals >= 2):
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading = next((line for line in lines if len(line) <= 80 and re.match(r"^(?:第?[一二三四五六七八九十0-9]+[章节.]|[0-9]+(?:\.[0-9]+){0,4}\s*|附录)", line)), f"PDF 第 {page_number} 页")
    parts, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > 1400 and len(current) >= 500:
            parts.append(current.strip()); current = ""
        current += ("\n" if current else "") + line
    if current.strip(): parts.append(current.strip())
    if len(parts) > 1 and len(parts[-1]) < 120:
        parts[-2] += "\n" + parts.pop()
    return [(heading, part) for part in parts if len(part) >= 80]


def main() -> None:
    manifest_path = RUNTIME / "chinese_manual_discovery.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy = KnowledgeLanguagePolicyService()
    imported, skipped, failed = [], [], []
    with SessionLocal() as db:
        for item in manifest["documents"]:
            if item.get("status") != "downloaded": continue
            existing = db.scalar(select(KnowledgeDocument).where(
                KnowledgeDocument.metadata_json["source_nid"].as_string() == item["nid"],
                KnowledgeDocument.metadata_json["parser_version"].as_string() == PARSER_VERSION,
                KnowledgeDocument.metadata_json["current_parse_version"].as_string() == "true",
            ))
            if existing:
                old_chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == existing.id)))
                quality_fix_needed = any("版权所有" in (chunk.content or "") for chunk in old_chunks)
                if not quality_fix_needed:
                    skipped.append({"nid": item["nid"], "document_id": str(existing.id), "reason": "current_parse_version_exists"}); continue
                old_metadata = dict(existing.metadata_json or {})
                old_metadata.update({"current_parse_version": False, "superseded": True,
                                     "superseded_reason": "header_footer_quality_fix"})
                existing.metadata_json = old_metadata
                for chunk in old_chunks:
                    chunk.status = "superseded"
                db.add(OperationLog(module="knowledge_parsing", action="parse_version_superseded",
                    target_type="knowledge_document", target_id=str(existing.id), operator="Development Engineering Reviewer",
                    detail={"parser_version": PARSER_VERSION, "reason": "header_footer_quality_fix",
                            "automatic": True, "chunks_retained": len(old_chunks)}))
                db.flush()
            try:
                reader = PdfReader(item["local_path"])
                pages = clean_pages(reader)
                candidates = []
                seen = set()
                for page_no, text in enumerate(pages, 1):
                    for heading, content in page_chunks(text, page_no):
                        digest = hashlib.sha256(normalized(content).encode("utf-8")).hexdigest()
                        if digest in seen: continue
                        seen.add(digest); candidates.append((page_no, heading, content, digest))
                combined_sample = "\n".join(content for _, _, content, _ in candidates[:80])
                metadata = policy.policy_metadata(metadata={
                    "language": "zh-CN", "source_nid": item["nid"], "source_url": item["source_url"],
                    "official_source": True, "official_domain": "support.huawei.com",
                    "source_provenance": "VENDOR_OFFICIAL", "product_family": item["product_family"],
                    "equipment_categories": item["equipment"], "document_type_normalized": item["document_type"],
                    "parser_version": PARSER_VERSION, "chunker_version": "semantic_manual_zh_v2",
                    "parse_iteration": int((existing.metadata_json or {}).get("parse_iteration") or 1) + 1 if existing else 1,
                    "parser_success": True, "current_parse_version": True, "superseded": False,
                    "quality_status": "QUALITY_GATE_CANDIDATE", "marketing_only": False,
                    "original_sha256": item["sha256"], "machine_translation_used": False,
                }, title=item["title"], content=combined_sample)
                if metadata["normalized_language"] != "zh-CN" or metadata["chinese_character_ratio"] < 0.60:
                    raise ValueError("PDF content did not satisfy Chinese-primary detection")
                document = KnowledgeDocument(title=item["title"][:255], manufacturer="huawei",
                    product_series=item["product_family"], device_type="pv_inverter",
                    document_type=item["document_type"], source=item["source_url"], source_type="vendor_official",
                    file_name=item.get("file_name") or f"{item['nid']}.pdf", file_path=item["local_path"],
                    file_size=item["file_size"], file_ext="pdf", page_count=len(reader.pages), parse_status="parsed",
                    parser_name=PARSER_VERSION, chunk_count=len(candidates), metadata_json=metadata,
                    parsed_at=datetime.now(timezone.utc), review_status="pending_review", status="active")
                db.add(document); db.flush()
                for index, (page_no, heading, content, digest) in enumerate(candidates):
                    db.add(KnowledgeChunk(document_id=document.id, manufacturer="huawei",
                        product_series=document.product_series, device_type=document.device_type,
                        document_type=document.document_type, chunk_index=index, content=content,
                        content_hash=digest, section_title=heading[:255], char_count=len(content), page_number=page_no,
                        embedding_status="pending", status="active", metadata_json={
                            "source_locator": {"page_number": page_no, "section": heading},
                            "heading_path": [heading], "parser_version": PARSER_VERSION,
                            "chunker_version": "semantic_manual_zh_v2", "current_chunk_version": True,
                            "content_hash_method": "sha256_normalized_text",
                        }))
                db.commit()
                imported.append({"nid": item["nid"], "document_id": str(document.id), "pages": len(reader.pages), "chunks": len(candidates)})
            except Exception as exc:
                db.rollback(); failed.append({"nid": item["nid"], "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
    write_json("chinese_manual_import.json", {"generated_at": now_iso(), "parser_version": PARSER_VERSION,
        "imported": imported, "skipped": skipped, "failed": failed,
        "new_parse_versions_only": True, "original_pdfs_retained": True})
    print({"status": "passed" if not failed else "passed_with_failures", "imported": len(imported), "skipped": len(skipped), "failed": len(failed), "chunks": sum(x["chunks"] for x in imported)})


if __name__ == "__main__": main()
