from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from task28a_path_safety import ALLOWED_PROJECT_ROOT, assert_project_path


CORPUS_ROOT = ALLOWED_PROJECT_ROOT / "knowledge_assets" / "competition_corpus_v1"
DEFAULT_INVENTORY = CORPUS_ROOT / "manifests" / "source_inventory.json"
DEFAULT_RAW_ROOT = CORPUS_ROOT / "raw"
DEFAULT_OUTPUT = CORPUS_ROOT / "manifests" / "knowledge_import_manifest.json"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_pdf_sample(path: Path, *, page_limit: int = 5) -> dict[str, Any]:
    reader = PdfReader(str(path))
    warnings: list[str] = []
    text_parts: list[str] = []
    for page_number, page in enumerate(reader.pages[:page_limit], start=1):
        try:
            text_parts.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 - preserve partial metadata extraction.
            warnings.append(f"page {page_number}: {type(exc).__name__}")
    metadata = {
        str(key).lstrip("/"): str(value)
        for key, value in dict(reader.metadata or {}).items()
        if value not in (None, "")
    }
    return {
        "text": "\n".join(text_parts),
        "page_count": len(reader.pages),
        "parser": "pypdf",
        "pdf_metadata": metadata,
        "warnings": warnings,
    }


def _extract_text_sample(path: Path) -> dict[str, Any]:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return {
                "text": path.read_text(encoding=encoding),
                "page_count": None,
                "parser": f"text:{encoding}",
                "pdf_metadata": {},
                "warnings": [],
            }
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode text document: {path.name}")


def _first_match(patterns: tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _normalize_text(match.group(1))
    return None


def _validated_version(value: str | None) -> str | None:
    if not value or not re.search(r"\d", value):
        return None
    return value


def _declared_source_file(text: str) -> str | None:
    return _first_match(
        (r"(?:来源文件|source\s+file)\s*[:：]\s*([^\r\n]+?\.(?:pdf|docx|txt|md))",),
        text,
    )


def _normalized_document_name(value: str) -> str:
    stem = Path(value).stem.casefold()
    stem = re.sub(r"\(\d+\)$", "", stem)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", stem)


def _document_type(text: str) -> str:
    compact = _normalize_text(text[:8000]).casefold()
    if "告警参考" in compact or "告警代码" in compact:
        return "alarm_code"
    if "快速指南" in compact:
        return "manual"
    if "调测指南" in compact or "设备替换" in compact:
        return "sop"
    if "用户手册" in compact or "user manual" in compact:
        return "manual"
    return "unknown_review_required"


def _evidence_lines(text: str, terms: tuple[str, ...], limit: int = 12) -> list[str]:
    result: list[str] = []
    for raw_line in text.splitlines():
        line = _normalize_text(raw_line)
        if not line or len(line) > 180:
            continue
        if any(term.casefold() in line.casefold() for term in terms) and line not in result:
            result.append(line)
        if len(result) >= limit:
            break
    return result


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = assert_project_path(path)
    assert_project_path(path.parent).mkdir(parents=True, exist_ok=True)
    temporary = assert_project_path(path.with_name(f".{path.name}.task28a.tmp"))
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def build_manifest(inventory_path: Path, raw_root: Path, output_path: Path) -> dict[str, Any]:
    inventory_path = assert_project_path(inventory_path, must_exist=True)
    raw_root = assert_project_path(raw_root, must_exist=True)
    output_path = assert_project_path(output_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    documents: list[dict[str, Any]] = []
    media_assets: list[dict[str, Any]] = []
    excluded_assets: list[dict[str, Any]] = []

    for record in inventory["records"]:
        relative = Path(*Path(record["relative_path"]).parts)
        path = assert_project_path(raw_root / relative, must_exist=True)
        category = record["category"]
        base = {
            "relative_path": record["relative_path"],
            "raw_path": str(path),
            "file_name": record["file_name"],
            "extension": record["extension"],
            "size_bytes": record["size_bytes"],
            "sha256": record["sha256"],
            "duplicate_of": record["suspected_duplicate_of"] or None,
        }
        if category in {"HUAWEI_DOCUMENT", "SUNGROW_FUTURE_DOCUMENT"}:
            try:
                extracted = (
                    _extract_pdf_sample(path)
                    if path.suffix.casefold() == ".pdf"
                    else _extract_text_sample(path)
                )
                sample = extracted["text"]
                extract_status = "sample_extracted" if _normalize_text(sample) else "empty_sample_review_required"
                extract_error = None
            except Exception as exc:  # noqa: BLE001 - manifest records review requirements.
                extracted = {"text": "", "page_count": None, "parser": None, "pdf_metadata": {}, "warnings": []}
                sample = ""
                extract_status = "failed"
                extract_error = f"{type(exc).__name__}: {exc}"

            is_huawei = category == "HUAWEI_DOCUMENT"
            manufacturer = "Huawei" if is_huawei else "Sungrow"
            manufacturer_normalized = "huawei" if is_huawei else "sungrow"
            product_family = "SUN2000" if is_huawei else "SG"
            scope = "huawei_sun2000_competition_v1" if is_huawei else "future_sungrow_scope"
            content_manufacturer_evidence = (
                any(term in sample.casefold() for term in ("华为", "huawei"))
                if is_huawei
                else any(term in sample.casefold() for term in ("阳光电源", "sungrow"))
            )
            product_evidence = product_family.casefold() in sample.casefold()
            document_version = _validated_version(_first_match(
                (r"文档版本\s*[:：]?\s*([^\s]+)", r"版本\s*[:：]\s*([^\s]+)"),
                sample,
            ))
            release_date = _first_match(
                (r"发布日期\s*[:：]?\s*([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})",),
                sample,
            )
            document_number = _first_match(
                (r"文档编号\s*[:：]?\s*([A-Za-z0-9._-]+)",),
                sample,
            )
            evidence_lines = _evidence_lines(sample, (manufacturer, product_family, "用户手册", "告警", "指南"))
            normalized_sample = _normalize_text(sample)
            replacement_ratio = (
                round(normalized_sample.count("\ufffd") / len(normalized_sample), 8)
                if normalized_sample
                else None
            )
            documents.append({
                **base,
                "title": path.stem,
                "manufacturer": manufacturer,
                "manufacturer_normalized": manufacturer_normalized,
                "product_family": product_family,
                "language": "zh-CN",
                "scope": scope,
                "source_type": "vendor_official" if is_huawei else "vendor_official_or_review_required",
                "review_status": "pending_review",
                "is_current_version": True if is_huawei else False,
                "is_formal_retrieval_candidate": True if is_huawei else False,
                "selected_for_test_import": (
                    extract_status == "sample_extracted"
                    and _document_type(sample) != "unknown_review_required"
                    and not bool(record["suspected_duplicate_of"])
                ),
                "alias_of_relative_path": None,
                "document_type": _document_type(sample),
                "detected_document_number": document_number,
                "detected_document_version": document_version,
                "detected_release_date": release_date,
                "model_evidence_lines": _evidence_lines(sample, ("SUN2000", "SG"), limit=20),
                "metadata_evidence": {
                    "manufacturer_found_in_sample": content_manufacturer_evidence,
                    "product_family_found_in_sample": product_evidence,
                    "document_identity_lines": evidence_lines,
                    "declared_source_file": _declared_source_file(sample),
                    "fields_without_content_evidence_remain_pending_review": True,
                },
                "parse_preflight": {
                    "status": extract_status,
                    "error": extract_error,
                    "parser": extracted["parser"],
                    "page_count": extracted["page_count"],
                    "sample_char_count": len(sample),
                    "sample_sha256": hashlib.sha256(sample.encode("utf-8")).hexdigest() if sample else None,
                    "replacement_character_ratio": replacement_ratio,
                    "warnings": extracted["warnings"],
                    "pdf_metadata": extracted["pdf_metadata"],
                },
            })
        elif category == "FAULT_IMAGE":
            case_id = {
                "报错01.jpg": "FAULT_CASE_01_PV_ISOLATION_LOW",
                "报错02.jpg": "FAULT_CASE_02_GRID_VOLTAGE_OUT_OF_RANGE",
            }.get(path.name)
            media_assets.append({
                **base,
                "asset_type": "fault_image",
                "case_id": case_id,
                "selected_for_multimodal_acceptance": case_id is not None,
                "ocr_status": "not_run",
                "vision_status": "not_run",
                "human_confirmation_status": "pending",
                "expert_review_required": True,
            })
        else:
            excluded_assets.append({
                **base,
                "category": category,
                "reason": "not a knowledge-document or multimodal upload candidate",
            })

    for document in documents:
        declared_source = document["metadata_evidence"].get("declared_source_file")
        if not declared_source:
            continue
        declared_identity = _normalized_document_name(declared_source)
        candidates = [
            candidate
            for candidate in documents
            if candidate is not document
            and candidate["manufacturer_normalized"] == document["manufacturer_normalized"]
            and candidate["extension"] == ".pdf"
            and _normalized_document_name(candidate["file_name"]) == declared_identity
        ]
        if len(candidates) != 1:
            document["metadata_evidence"]["declared_source_resolution"] = "manual_review_required"
            continue
        canonical = candidates[0]
        document["alias_of_relative_path"] = canonical["relative_path"]
        document["selected_for_test_import"] = False
        document["is_formal_retrieval_candidate"] = False
        document["is_current_version"] = False
        document["source_type"] = "derived_text_alias"
        document["metadata_evidence"]["declared_source_resolution"] = "resolved_to_migrated_pdf"

    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_id": "competition_corpus_v1",
        "raw_root": str(raw_root),
        "review_policy": {
            "default": "pending_review",
            "user_case_notes": "pending_expert_review",
            "sungrow_scope": "future_sungrow_scope",
            "sungrow_must_not_enter_huawei_scope": True,
            "images_use_media_multimodal_pipeline": True,
        },
        "counts": {
            "documents": len(documents),
            "huawei_documents": sum(item["manufacturer_normalized"] == "huawei" for item in documents),
            "sungrow_future_documents": sum(item["manufacturer_normalized"] == "sungrow" for item in documents),
            "media_assets": len(media_assets),
            "excluded_assets": len(excluded_assets),
            "preflight_failures": sum(item["parse_preflight"]["status"] == "failed" for item in documents),
        },
        "documents": documents,
        "media_assets": media_assets,
        "excluded_assets": excluded_assets,
    }
    _atomic_json(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Task 28A knowledge and media import metadata")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_manifest(args.inventory, args.raw_root, args.output)
    print(json.dumps({
        "status": "manifest_created",
        "counts": result["counts"],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
