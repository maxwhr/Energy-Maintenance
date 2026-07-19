from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25b_r2_u3_r3_dev"
DOWNLOADS = RUNTIME / "downloads"
RUNTIME.mkdir(parents=True, exist_ok=True)
DOWNLOADS.mkdir(parents=True, exist_ok=True)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

RULE_VERSION = "task25b_r2_u3_r3_dev_v1"
PARSER_VERSION = "huawei_pdf_structured_zh_v2"
OFFICIAL_DOMAINS = {
    "support.huawei.com", "download.huawei.com", "support-download.huawei.com",
    "fusionsolar.huawei.com", "intl.fusionsolar.huawei.com", "solar.huawei.com",
    "digitalpower.huawei.com", "info.support.huawei.com", "huawei.com",
}

MANUAL_SPECS = [
    {"nid": "EDOC1100108366", "product_family": "SmartLogger", "equipment": ["communication_device", "plant_controller"], "document_type": "USER_MANUAL"},
    {"nid": "EDOC1100270192", "product_family": "SUN2000", "equipment": ["pv_inverter"], "document_type": "USER_MANUAL"},
    {"nid": "EDOC1100059933", "product_family": "SUN2000", "equipment": ["pv_inverter"], "document_type": "INSTALLATION_GUIDE"},
    {"nid": "EDOC1100022346", "product_family": "SUN2000", "equipment": ["pv_inverter"], "document_type": "MAINTENANCE_GUIDE"},
    {"nid": "EDOC1100253089", "product_family": "SUN2000", "equipment": ["pv_inverter"], "document_type": "USER_MANUAL"},
    {"nid": "EDOC1100186675", "product_family": "LUNA2000", "equipment": ["energy_storage"], "document_type": "QUICK_GUIDE"},
    {"nid": "EDOC1100083811", "product_family": "FusionSolar", "equipment": ["management_platform", "communication_device"], "document_type": "OPERATION_GUIDE"},
    {"nid": "EDOC1100277791", "product_family": "LUNA2000", "equipment": ["energy_storage", "plant_controller"], "document_type": "USER_MANUAL"},
    {"nid": "EDOC1100167259", "product_family": "LUNA2000", "equipment": ["energy_storage"], "document_type": "USER_MANUAL"},
    {"nid": "EDOC1100273863", "product_family": "FusionSolar", "equipment": ["management_platform", "communication_device"], "document_type": "COMMISSIONING_GUIDE"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u4dbf\u4e00-\u9fff]+", "", (text or "").lower())


def official_url(url: str | None) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == item or host.endswith("." + item) for item in OFFICIAL_DOMAINS)


def write_json(name: str, payload: object) -> Path:
    path = RUNTIME / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def chunk_quality(document, chunks) -> dict:
    count = len(chunks)
    norm = [normalized(item.content) for item in chunks]
    hashes = [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in norm]
    exact = sum(value - 1 for value in Counter(hashes).values() if value > 1)
    near = 0
    # Conservative near-duplicate signal: same 160-char prefix and similar length.
    prefixes: dict[str, list[int]] = {}
    for value in norm:
        prefixes.setdefault(value[:160], []).append(len(value))
    for lengths in prefixes.values():
        if len(lengths) > 1 and max(lengths) and min(lengths) / max(lengths) >= 0.9:
            near += len(lengths) - 1
    locator = sum(bool((item.metadata_json or {}).get("source_locator")) for item in chunks)
    pages = sum(item.page_number is not None for item in chunks)
    headings = sum(bool(item.section_title or (item.metadata_json or {}).get("heading_path")) for item in chunks)
    empty = sum(not (item.content or "").strip() for item in chunks)
    short = sum(0 < len((item.content or "").strip()) < 80 for item in chunks)
    combined = "\n".join(item.content or "" for item in chunks)
    noise = len(re.findall(r"版权所有|all rights reserved|隐私声明|cookie|目录\s*\.\s*\.\s*\.", combined, re.I))
    alarms = len(set(re.findall(r"(?<!\d)(?:20\d{2}|30\d{2}|40\d{2}|50\d{2})(?!\d)", combined)))
    trouble = len(re.findall(r"故障处理|排障|处理步骤|处理建议|可能原因", combined))
    safety = len(re.findall(r"危险|警告|注意|安全要求|断开.{0,12}电源|禁止带电", combined))
    return {
        "chunk_count": count, "exact_duplicate_count": exact, "near_duplicate_count": near,
        "exact_duplicate_ratio": round(exact / count, 6) if count else 0,
        "near_duplicate_ratio": round(near / count, 6) if count else 0,
        "locator_coverage": round(locator / count, 6) if count else 0,
        "page_coverage": round(pages / count, 6) if count else 0,
        "heading_coverage": round(headings / count, 6) if count else 0,
        "empty_chunk_count": empty, "very_short_chunk_count": short,
        "very_short_ratio": round(short / count, 6) if count else 0,
        "noise_count": noise, "alarm_identifiers": alarms,
        "troubleshooting_sections": trouble, "safety_sections": safety,
    }


def quality_decision(document, chunks) -> tuple[bool, list[str], dict]:
    metadata = document.metadata_json or {}
    metrics = chunk_quality(document, chunks)
    reasons = []
    if metadata.get("normalized_language") != "zh-CN": reasons.append("language_not_zh-CN")
    if metadata.get("source_provenance") not in {"VENDOR_OFFICIAL", "VENDOR_OFFICIAL_ZH"}: reasons.append("not_vendor_official")
    if not official_url(document.source or metadata.get("source_url")): reasons.append("invalid_official_source_url")
    if metadata.get("quality_status") in {"NEEDS_METADATA", "UNKNOWN_SOURCE"}: reasons.append("metadata_or_source_blocked")
    if metadata.get("marketing_only"): reasons.append("marketing_only")
    if not metadata.get("parser_success", document.parse_status == "parsed"): reasons.append("parser_failed")
    if not metrics["chunk_count"]: reasons.append("no_chunks")
    if any(not item.content_hash for item in chunks): reasons.append("missing_content_hash")
    if metrics["exact_duplicate_ratio"] >= 0.01: reasons.append("exact_duplicate_ratio_not_below_1_percent")
    if metrics["near_duplicate_ratio"] >= 0.05: reasons.append("near_duplicate_ratio_not_below_5_percent")
    if metrics["locator_coverage"] < 0.98: reasons.append("locator_coverage_below_98_percent")
    is_html_faq = document.document_type == "FAQ_TROUBLESHOOTING"
    if not is_html_faq and metrics["page_coverage"] < 0.95: reasons.append("page_coverage_below_95_percent")
    if metrics["heading_coverage"] < 0.90: reasons.append("heading_coverage_below_90_percent")
    if metrics["empty_chunk_count"]: reasons.append("empty_chunks")
    if not is_html_faq and metrics["very_short_ratio"] >= 0.05: reasons.append("very_short_ratio_not_below_5_percent")
    if metrics["noise_count"]: reasons.append("navigation_header_footer_noise")
    if not document.product_series or not metadata.get("equipment_categories"): reasons.append("incomplete_product_or_equipment_metadata")
    if float(metadata.get("chinese_character_ratio") or 0) < 0.60: reasons.append("chinese_ratio_below_60_percent")
    score = max(0, 100 - len(reasons) * 12)
    metrics["quality_score"] = score
    return not reasons, reasons, metrics
