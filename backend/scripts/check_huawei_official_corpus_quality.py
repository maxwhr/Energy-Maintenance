from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from task25b_r2_u2_common import BACKEND, ROOT, RUNTIME, now_iso, write_csv, write_json


MODEL_PATTERN = re.compile(r"\b(?:SUN2000|LUNA2000|MERC|SmartGuard|SmartLogger|SmartACU|SPPC|SPMS)[A-Za-z0-9/().-]*", re.I)
ALARM_PATTERN = re.compile(r"\b(?:ALM[-_ ]?\d{3,6}|alarm\s*(?:id|code)?\s*[:#]?\s*\d{3,6}|告警(?:码|ID)?\s*[:：]?\s*\d{3,6})\b", re.I)


def count_terms(text: str, terms: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(term.lower()) for term in terms)


def infer_document_type(title: str, text: str, declared: str) -> str:
    sample = (title + " " + text[:8000]).lower()
    if "quick guide" in sample or "quickguide" in sample:
        return "QUICK_GUIDE"
    if "user manual" in sample or "user guide" in sample:
        return "USER_MANUAL"
    if "maintenance" in sample:
        return "MAINTENANCE_GUIDE"
    if "installation" in sample:
        return "INSTALLATION_GUIDE"
    if "datasheet" in sample or "technical specification" in sample:
        return "DATASHEET"
    return declared


def inspect_pdf(path: Path, manifest: dict) -> dict:
    try:
        reader = PdfReader(path)
        page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n".join(page_texts)
        pages = len(reader.pages)
        blank = sum(len(value) < 20 for value in page_texts)
        normalized = [re.sub(r"\s+", " ", value).strip().lower() for value in page_texts if len(value) >= 50]
        duplicates = sum(value - 1 for value in Counter(normalized).values() if value > 1)
        image_count = 0
        for page in reader.pages:
            resources = page.get("/Resources") or {}
            xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
            try:
                image_count += len(xobjects.get_object()) if xobjects else 0
            except Exception:
                pass
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        visible = len(re.findall(r"\S", text)) or 1
        models = sorted(set(MODEL_PATTERN.findall(text)))
        alarms = sorted(set(ALARM_PATTERN.findall(text)))
        safety = count_terms(text, ("warning", "danger", "caution", "safety", "警告", "危险", "安全"))
        install = count_terms(text, ("installation", "installing", "mounting", "安装"))
        maintenance = count_terms(text, ("maintenance", "replacement", "replace", "troubleshooting", "维护", "更换", "故障"))
        tables = len(re.findall(r"(?:Table|表)\s*[A-Z0-9-]+", text, re.I))
        gibberish = text.count("�") / visible
        scanned = len(text) < max(500, pages * 80)
        declared_type = manifest.get("document_type") or "TECHNICAL_DOCUMENT"
        dtype = infer_document_type(manifest.get("document_title") or path.stem, text, declared_type)
        marketing = dtype == "DATASHEET" or (
            pages <= 4 and safety == 0 and install < 2 and maintenance < 2
        )
        if scanned:
            status = "REQUIRES_OCR"
        elif gibberish > 0.02 or not text.strip():
            status = "REQUIRES_MANUAL_REVIEW"
        elif marketing:
            status = "MARKETING_ONLY"
        elif dtype in {"USER_MANUAL", "INSTALLATION_GUIDE", "QUICK_GUIDE", "MAINTENANCE_GUIDE", "ALARM_REFERENCE", "TROUBLESHOOTING_GUIDE", "PART_REPLACEMENT_GUIDE", "COMMISSIONING_GUIDE", "SAFETY_GUIDE", "COMMUNICATION_GUIDE", "TECHNICAL_DOCUMENT"}:
            status = "READY_FOR_DRAFT_IMPORT"
        else:
            status = "REQUIRES_MANUAL_REVIEW"
        return {
            **manifest, "quality_status": status, "document_type": dtype,
            "openable": True, "page_count": pages, "paragraph_count": len([line for line in text.splitlines() if line.strip()]),
            "heading_count": len(re.findall(r"(?m)^(?:\d+(?:\.\d+)*\s+|[A-Z][A-Z ]{4,}$)", text)),
            "table_count": tables, "image_count": image_count, "ocr_required": scanned,
            "chinese_text_ratio": round(chinese / visible, 6), "device_models": models[:100],
            "model_code_count": len(models), "alarm_codes": alarms[:200], "alarm_code_count": len(alarms),
            "safety_section_count": safety, "installation_step_count": install, "maintenance_step_count": maintenance,
            "duplicate_pages": duplicates, "blank_pages": blank, "gibberish_ratio": round(gibberish, 6),
            "scanned_pdf": scanned, "version_duplicate": manifest.get("status") == "DUPLICATE",
            "language_duplicate": False, "marketing_only": marketing, "extracted_character_count": len(text),
        }
    except Exception as exc:
        return {**manifest, "quality_status": "INVALID_FILE", "openable": False, "error": type(exc).__name__}


def main() -> int:
    download = json.loads((RUNTIME / "huawei_download_result.json").read_text(encoding="utf-8"))
    rows = []
    for item in download.get("manifest", []):
        if item.get("status") != "DOWNLOADED":
            continue
        path = BACKEND / item["relative_file_path"].replace("storage/", "storage/")
        rows.append(inspect_pdf(path, item) if item.get("file_type") == "pdf" else {
            **item, "quality_status": "REQUIRES_MANUAL_REVIEW", "openable": True, "ocr_required": False,
        })
    counts = Counter(item["quality_status"] for item in rows)
    payload = {
        "generated_at": now_iso(), "files_checked": len(rows), "quality_status_counts": dict(counts),
        "ready_for_draft_import": counts.get("READY_FOR_DRAFT_IMPORT", 0),
        "requires_ocr": counts.get("REQUIRES_OCR", 0), "requires_manual_review": counts.get("REQUIRES_MANUAL_REVIEW", 0),
        "marketing_only": counts.get("MARKETING_ONLY", 0), "invalid": counts.get("INVALID_FILE", 0),
        "total_pages": sum(int(item.get("page_count") or 0) for item in rows),
        "model_codes": len({model for item in rows for model in item.get("device_models", [])}),
        "alarm_codes": len({code for item in rows for code in item.get("alarm_codes", [])}),
        "safety_sections": sum(int(item.get("safety_section_count") or 0) for item in rows),
        "records": rows,
    }
    write_json("huawei_corpus_quality.json", payload)
    fields = [
        "file_sha256", "relative_file_path", "document_title", "product_family", "document_type", "language",
        "quality_status", "page_count", "paragraph_count", "heading_count", "table_count", "image_count",
        "ocr_required", "chinese_text_ratio", "model_code_count", "alarm_code_count", "safety_section_count",
        "installation_step_count", "maintenance_step_count", "duplicate_pages", "blank_pages", "gibberish_ratio",
        "scanned_pdf", "version_duplicate", "language_duplicate", "marketing_only", "extracted_character_count",
    ]
    write_csv("huawei_corpus_quality.csv", fields, rows)
    print(json.dumps({key: payload[key] for key in ("files_checked", "ready_for_draft_import", "requires_ocr", "requires_manual_review", "marketing_only", "invalid", "total_pages", "model_codes", "alarm_codes", "safety_sections")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
