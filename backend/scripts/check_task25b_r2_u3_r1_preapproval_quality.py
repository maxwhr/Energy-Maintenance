from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
U3_RUNTIME = ROOT / ".runtime" / "task25b_r2_u3"
RUNTIME = ROOT / ".runtime" / "task25b_r2_u3_r1"
REPORT = ROOT / "docs" / "25B_R2_U3_R1_preapproval_quality_audit.md"
RUNTIME.mkdir(parents=True, exist_ok=True)

DECISIONS = {
    "RECOMMEND_APPROVE",
    "REQUIRE_INDIVIDUAL_REVIEW",
    "NEEDS_METADATA",
    "NEEDS_REPARSE",
    "REJECT_DUPLICATE",
    "REJECT_MARKETING",
    "REJECT_INVALID",
}
CHECKLIST_FIELDS = [
    "document_id", "masked_title", "source_url", "official_domain", "product_family",
    "equipment_category", "document_type", "version", "language", "page_count", "chunk_count",
    "median_chunk_length", "min_chunk_length", "max_chunk_length", "empty_chunk_count",
    "very_short_chunk_count", "duplicate_chunk_count", "near_duplicate_chunk_count",
    "source_locator_coverage", "page_number_coverage", "heading_path_coverage", "table_chunk_count",
    "navigation_noise_count", "footer_noise_count", "encoding_issue_count", "alarm_count",
    "troubleshooting_count", "safety_action_count", "quality_score", "decision", "decision_reasons",
]
NO_ANSWER_QUERIES = [
    "第三方燃煤锅炉给煤机振动告警如何按华为逆变器手册复位？",
    "柴油发电机机油压力低时应查询哪个 SUN2000 告警码？",
    "家用空调压缩机结霜是否属于 LUNA2000 储能故障？",
    "汽车 ABS 灯亮时应在 FusionSolar 中执行什么检修步骤？",
    "非华为充电桩显示 E999，华为 SmartLogger 手册如何处理？",
    "风力发电机齿轮箱油温高是否应更换 SUN2000 功率模块？",
    "电梯门机通信中断对应哪个 SmartGuard 告警？",
    "燃气轮机叶片裂纹能否通过华为光伏逆变器 FAQ 诊断？",
    "水泵轴承异响属于 LUNA2000 电池簇哪种告警？",
    "铁路信号机红灯常亮应查询哪个 SUN2000 章节？",
    "第三方 UPS 电池鼓包是否可直接套用华为储能熔丝更换步骤？",
]
HARD_NEGATIVE_QUERIES = [
    ("SUN2000 已完全断开交流和直流电源，但查询要求设备继续带电运行并立即拆卸端子，应如何操作？", "安全条件互相矛盾，不能给出带电拆卸步骤"),
    ("LUNA2000 电池 SOC 正常且无告警，但查询断言必须更换全部电池模组，依据是什么？", "症状与强制更换结论不一致"),
    ("SmartLogger 通信正常且所有设备在线，却要求按通信中断故障处置，应该执行哪一步？", "设备状态与故障前提矛盾"),
    ("逆变器绝缘阻抗正常且无接地告警，能否直接判定存在低绝缘故障？", "检测结果与故障判断矛盾"),
    ("设备型号明确为第三方风机控制器，要求返回 SUN2000 专用告警代码，答案是什么？", "设备类型越界且不得伪造代码"),
    ("SmartGuard 未安装，却要求执行 SmartGuard 并离网切换复位，应该如何完成？", "目标设备不存在"),
    ("现场未提供型号、告警、指示灯或测量数据，要求唯一确定故障部件，结论是什么？", "证据不足，不能唯一诊断"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(name: str, payload: object) -> Path:
    path = RUNTIME / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def write_csv(name: str, fields: list[str], rows: list[dict]) -> Path:
    path = RUNTIME / name
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (list, dict)) else row.get(key) for key in fields})
    return path


def normalized(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())


def masked_title(value: str) -> str:
    value = " ".join((value or "").split())
    return value if len(value) <= 64 else f"{value[:44]}…{value[-14:]}"


def simhash64(value: str) -> int:
    text = normalized(value)
    grams = [text[index:index + 3] for index in range(max(1, len(text) - 2))] if text else [""]
    weights = [0] * 64
    for gram in grams:
        number = int.from_bytes(hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if number & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            result |= 1 << bit
    return result


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def percentage(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def locator_available(chunk: KnowledgeChunk) -> bool:
    metadata = chunk.metadata_json or {}
    locator = metadata.get("source_locator") or metadata.get("section_locator")
    return bool(locator and any(value not in (None, "", []) for value in locator.values()))


def noise_flags(content: str) -> tuple[bool, bool, bool]:
    lines = [line.strip() for line in (content or "").splitlines() if line.strip()]
    nav_pattern = re.compile(r"^(home|products?|support|downloads?|contact us|privacy|menu|breadcrumb|首页|产品|支持|下载中心|联系我们)$", re.I)
    footer_pattern = re.compile(r"copyright|all rights reserved|privacy policy|cookie policy|版权所有|隐私政策", re.I)
    navigation = sum(bool(nav_pattern.search(line)) for line in lines) >= 2
    footer = any(footer_pattern.search(line) for line in lines)
    encoding = bool(re.search(r"�|锟斤拷|Ã.|Â.|â€™|â€œ|â€", content or ""))
    return navigation, footer, encoding


def table_like(content: str) -> bool:
    text = content or ""
    markdown_rows = sum(1 for line in text.splitlines() if line.count("|") >= 2)
    structured_alarm = bool(re.search(r"(?i)(alarm id|alarm name|severity|possible cause|suggestion|告警ID|告警名称|可能原因|处理建议)", text))
    return markdown_rows >= 2 or structured_alarm


def language_class(content: str) -> str:
    text = content or ""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk > latin * 0.25:
        return "zh_or_mixed"
    return "latin"


def repeated_header_count(chunks: list[KnowledgeChunk]) -> int:
    first_lines = []
    for chunk in chunks:
        lines = [line.strip() for line in (chunk.content or "").splitlines() if line.strip()]
        if lines:
            first_lines.append(normalized(lines[0])[:120])
    counts = Counter(item for item in first_lines if len(item) >= 12)
    return sum(count - 1 for count in counts.values() if count >= 3)


def duplicate_metrics(chunks: list[KnowledgeChunk]) -> tuple[int, int, list[tuple[int, int]]]:
    hashes: dict[str, int] = {}
    exact = 0
    exact_pairs: set[tuple[int, int]] = set()
    normalized_values = []
    simhashes = []
    for index, chunk in enumerate(chunks):
        value = normalized(chunk.content)
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        if digest in hashes:
            exact += 1
            exact_pairs.add((hashes[digest], index))
        else:
            hashes[digest] = index
        normalized_values.append(value)
        simhashes.append(simhash64(value))
    near_indices: set[int] = set()
    near_pairs: list[tuple[int, int]] = []
    for left in range(len(chunks)):
        for right in range(left + 1, len(chunks)):
            if normalized_values[left] == normalized_values[right]:
                continue
            left_len, right_len = len(normalized_values[left]), len(normalized_values[right])
            if not left_len or min(left_len, right_len) / max(left_len, right_len) < 0.85:
                continue
            if hamming(simhashes[left], simhashes[right]) <= 3:
                near_indices.add(right)
                near_pairs.append((left, right))
    return exact, len(near_indices), near_pairs


def decision_for(metrics: dict, metadata: dict, source_type: str) -> tuple[str, list[str], int]:
    reasons: list[str] = []
    chunk_count = metrics["chunk_count"]
    exact_ratio = percentage(metrics["duplicate_chunk_count"], chunk_count)
    near_ratio = percentage(metrics["near_duplicate_chunk_count"], chunk_count)
    locator_or_page = max(metrics["source_locator_coverage"], metrics["page_number_coverage"])
    score = 100.0
    score -= min(30, metrics["empty_chunk_count"] * 10)
    score -= 20 * percentage(metrics["very_short_chunk_count"], chunk_count)
    score -= 30 * exact_ratio
    score -= 20 * near_ratio
    score -= 15 * (1 - locator_or_page)
    score -= 10 * (1 - metrics["heading_path_coverage"])
    score -= min(10, metrics["navigation_noise_count"] + metrics["footer_noise_count"])
    score -= min(20, metrics["encoding_issue_count"] * 5)
    if not metrics["source_url"]:
        score -= 25
        reasons.append("missing_source_url")
    score_int = max(0, min(100, round(score)))
    if metadata.get("marketing_only"):
        return "REJECT_MARKETING", ["marketing_only"], score_int
    if metadata.get("duplicate") or exact_ratio >= 0.25:
        return "REJECT_DUPLICATE", ["document_or_chunk_duplicate"], score_int
    if not chunk_count or metrics["empty_chunk_count"]:
        return "REJECT_INVALID", ["empty_document_or_chunk"], score_int
    if metrics["encoding_issue_count"] > max(2, math.ceil(chunk_count * 0.02)):
        return "NEEDS_REPARSE", ["encoding_issue_threshold"], score_int
    if source_type == "vendor_official" or metadata.get("quality_status") == "READY_FOR_DRAFT_IMPORT":
        reasons.append("u2_pdf_requires_individual_review")
    if metadata.get("product_family") == "SmartLogger":
        reasons.append("smartlogger_long_document_special_audit")
    if near_ratio >= 0.05:
        reasons.append("near_duplicate_ratio_at_or_above_5_percent")
    if locator_or_page < 0.95:
        reasons.append("source_locator_or_page_coverage_below_95_percent")
    if percentage(metrics["very_short_chunk_count"], chunk_count) > 0.20:
        reasons.append("very_short_chunk_ratio_above_20_percent")
    if score_int < 80:
        reasons.append("quality_score_below_80")
    if reasons:
        return "REQUIRE_INDIVIDUAL_REVIEW", reasons, score_int
    return "RECOMMEND_APPROVE", ["quality_thresholds_passed"], score_int


def document_row(document: KnowledgeDocument, chunks: list[KnowledgeChunk]) -> dict:
    metadata = document.metadata_json or {}
    lengths = [len(chunk.content or "") for chunk in chunks]
    exact_count, near_count, _ = duplicate_metrics(chunks)
    nav = footer = encoding = tables = 0
    for chunk in chunks:
        chunk_nav, chunk_footer, chunk_encoding = noise_flags(chunk.content)
        nav += int(chunk_nav)
        footer += int(chunk_footer)
        encoding += int(chunk_encoding)
        tables += int(table_like(chunk.content))
    alarm = metadata.get("alarm_knowledge") or {}
    metrics = {
        "document_id": str(document.id),
        "masked_title": masked_title(document.title),
        "source_url": document.source or metadata.get("source_url") or "",
        "official_domain": urlparse(document.source or metadata.get("source_url") or "").hostname or "",
        "product_family": metadata.get("product_family") or document.product_series or "",
        "equipment_category": metadata.get("equipment_categories") or [],
        "document_type": document.document_type,
        "version": metadata.get("document_version") or "",
        "language": metadata.get("language") or "",
        "page_count": document.page_count,
        "chunk_count": len(chunks),
        "median_chunk_length": round(statistics.median(lengths), 1) if lengths else 0,
        "min_chunk_length": min(lengths) if lengths else 0,
        "max_chunk_length": max(lengths) if lengths else 0,
        "empty_chunk_count": sum(length == 0 for length in lengths),
        "very_short_chunk_count": sum(0 < length < 80 for length in lengths),
        "duplicate_chunk_count": exact_count,
        "near_duplicate_chunk_count": near_count,
        "source_locator_coverage": percentage(sum(locator_available(chunk) for chunk in chunks), len(chunks)),
        "page_number_coverage": percentage(sum(chunk.page_number is not None for chunk in chunks), len(chunks)),
        "heading_path_coverage": percentage(sum(bool((chunk.section_title or "").strip()) for chunk in chunks), len(chunks)),
        "table_chunk_count": tables,
        "navigation_noise_count": nav,
        "footer_noise_count": footer,
        "encoding_issue_count": encoding,
        "alarm_count": len(alarm.get("explicit_alarm_codes") or []) + len(alarm.get("named_alarms") or []),
        "troubleshooting_count": int(alarm.get("troubleshooting_steps") or 0),
        "safety_action_count": int(alarm.get("safety_actions") or metadata.get("safety_section_count") or 0),
    }
    decision, reasons, score = decision_for(metrics, metadata, document.source_type)
    metrics.update(quality_score=score, decision=decision, decision_reasons=reasons)
    assert decision in DECISIONS
    return metrics


def needs_metadata_rows(quality_records: list[dict], internal_records: list[dict]) -> list[dict]:
    internal_by_hash = {item.get("content_hash"): item for item in internal_records}
    rows = []
    for item in quality_records:
        if item.get("quality_status") != "NEEDS_METADATA":
            continue
        source = internal_by_hash.get(item.get("content_hash"), item)
        content = source.get("content") or ""
        rows.append({
            "document_id": f"candidate:{item.get('content_hash', '')[:16]}",
            "masked_title": masked_title(f"{item.get('product_family', '')} FAQ - {item.get('question_title', '')}"),
            "source_url": item.get("source_url") or "", "official_domain": urlparse(item.get("source_url") or "").hostname or "",
            "product_family": item.get("product_family") or "", "equipment_category": item.get("equipment_categories") or [],
            "document_type": item.get("document_type") or "FAQ_TROUBLESHOOTING", "version": item.get("document_version") or "",
            "language": item.get("language") or "", "page_count": None, "chunk_count": 0,
            "median_chunk_length": len(content), "min_chunk_length": len(content), "max_chunk_length": len(content),
            "empty_chunk_count": int(not content.strip()), "very_short_chunk_count": int(0 < len(content) < 80),
            "duplicate_chunk_count": 0, "near_duplicate_chunk_count": 0,
            "source_locator_coverage": 1.0 if item.get("source_locator_available") else 0.0,
            "page_number_coverage": 0.0, "heading_path_coverage": 1.0 if item.get("question_title") else 0.0,
            "table_chunk_count": int(table_like(content)), "navigation_noise_count": int(noise_flags(content)[0]),
            "footer_noise_count": int(noise_flags(content)[1]), "encoding_issue_count": int(noise_flags(content)[2]),
            "alarm_count": len((item.get("alarm_knowledge") or {}).get("explicit_alarm_codes") or []) + len((item.get("alarm_knowledge") or {}).get("named_alarms") or []),
            "troubleshooting_count": int((item.get("alarm_knowledge") or {}).get("troubleshooting_steps") or 0),
            "safety_action_count": int((item.get("alarm_knowledge") or {}).get("safety_actions") or 0),
            "quality_score": 45, "decision": "NEEDS_METADATA",
            "decision_reasons": item.get("quality_reasons") or ["not_imported_not_approval_eligible"],
        })
    return rows


def smartlogger_audit(documents: list[KnowledgeDocument], chunks_by_document: dict[str, list[KnowledgeChunk]], rows_by_id: dict[str, dict]) -> dict:
    results = []
    for document in documents:
        metadata = document.metadata_json or {}
        if metadata.get("product_family") != "SmartLogger":
            continue
        chunks = chunks_by_document[str(document.id)]
        row = rows_by_id[str(document.id)]
        _, _, near_pairs = duplicate_metrics(chunks)
        seed = int(hashlib.sha256(str(document.id).encode("utf-8")).hexdigest()[:16], 16)
        generator = random.Random(seed)
        sample_indexes = sorted(generator.sample(range(len(chunks)), 20)) if len(chunks) >= 20 else list(range(len(chunks)))
        samples = []
        for index in sample_indexes:
            chunk = chunks[index]
            nav, footer, encoding = noise_flags(chunk.content)
            samples.append({
                "chunk_id": str(chunk.id), "chunk_index": chunk.chunk_index,
                "section_title": chunk.section_title, "source_locator": (chunk.metadata_json or {}).get("source_locator"),
                "excerpt": " ".join((chunk.content or "").split())[:280], "table_like": table_like(chunk.content),
                "language_class": language_class(chunk.content), "sample_method": "seeded_random_without_replacement",
                "navigation_noise": nav, "footer_noise": footer, "encoding_issue": encoding,
                "manual_review_result": "", "notes": "",
            })
        alarm_patterns = {
            "identifier": r"(?i)alarm\s*(id|code)|告警\s*(ID|码|代码)|\b\d{4,6}\b",
            "name": r"(?i)alarm\s*name|告警名称|fault\s*name|故障名称",
            "cause": r"(?i)possible\s*cause|cause|可能原因|原因",
            "impact": r"(?i)impact|effect|影响",
            "suggestion": r"(?i)suggestion|recommended\s*action|handling|处理建议|处理步骤|建议",
        }
        field_presence = {
            field: sum(bool(re.search(pattern, chunk.content or "")) for chunk in chunks)
            for field, pattern in alarm_patterns.items()
        }
        alarm_association = sum(
            sum(bool(re.search(pattern, chunk.content or "")) for pattern in alarm_patterns.values()) >= 3
            for chunk in chunks
        )
        chinese_english_duplicate_pairs = 0
        for left, right in near_pairs:
            if language_class(chunks[left].content) != language_class(chunks[right].content):
                chinese_english_duplicate_pairs += 1
        toc_noise = sum(bool(re.search(r"(?im)^\s*(table of contents|contents|目录)\s*$", chunk.content or "")) for chunk in chunks)
        copyright_noise = sum(bool(re.search(r"(?i)copyright|all rights reserved|版权所有", chunk.content or "")) for chunk in chunks)
        adjacent_context_gaps = 0
        for left, right in zip(chunks, chunks[1:]):
            if left.section_title == right.section_title:
                left_tail, right_head = normalized(left.content)[-100:], normalized(right.content)[:100]
                if left_tail and right_head and SequenceMatcher(None, left_tail, right_head).find_longest_match().size < 12:
                    adjacent_context_gaps += 1
        exact_ratio = percentage(row["duplicate_chunk_count"], row["chunk_count"])
        near_ratio = percentage(row["near_duplicate_chunk_count"], row["chunk_count"])
        passes = exact_ratio < 0.01 and near_ratio < 0.05 and row["source_locator_coverage"] >= 0.95
        results.append({
            "document_id": str(document.id), "masked_title": row["masked_title"], "chunk_count": len(chunks),
            "sample_count": len(samples), "table_chunk_count": row["table_chunk_count"],
            "sample_method": "seeded_random_without_replacement", "sample_seed_sha256": hashlib.sha256(str(document.id).encode("utf-8")).hexdigest(),
            "alarm_structure_field_presence": field_presence, "alarm_association_chunk_count": alarm_association,
            "chinese_english_near_duplicate_pairs": chinese_english_duplicate_pairs,
            "toc_noise_count": toc_noise, "copyright_noise_count": copyright_noise,
            "repeated_header_count": repeated_header_count(chunks), "adjacent_context_gap_candidates": adjacent_context_gaps,
            "exact_duplicate_ratio": exact_ratio, "near_duplicate_ratio": near_ratio,
            "source_locator_coverage": row["source_locator_coverage"], "near_duplicate_pairs": near_pairs[:50],
            "thresholds_passed": passes, "decision": "REQUIRE_INDIVIDUAL_REVIEW", "samples": samples,
        })
    return {"generated_at": now_iso(), "documents": results, "combined_chunks": sum(item["chunk_count"] for item in results), "automatic_approval": False}


def faq_duplicate_audit(quality_records: list[dict], internal_records: list[dict], id_by_key: dict[tuple[str, str], str]) -> dict:
    internal_by_hash = {item.get("content_hash"): item for item in internal_records}
    faqs = []
    for item in quality_records:
        if item.get("document_type") != "FAQ_TROUBLESHOOTING":
            continue
        source = internal_by_hash.get(item.get("content_hash"), item)
        content = source.get("content") or ""
        key = (item.get("content_hash") or "", item.get("source_url") or "")
        faqs.append({
            "document_id": id_by_key.get(key, f"candidate:{(item.get('content_hash') or '')[:16]}"),
            "title": item.get("question_title") or "", "content": content, "source_url": item.get("source_url") or "",
            "product_family": item.get("product_family") or "", "device_models": item.get("device_models") or [],
            "language": item.get("language") or "", "section_locator": item.get("section_locator") or {},
            "normalized_content_hash": hashlib.sha256(normalized(content).encode("utf-8")).hexdigest(),
            "simhash": f"{simhash64(content):016x}", "quality_status": item.get("quality_status"),
        })
    edges = []
    for left in range(len(faqs)):
        for right in range(left + 1, len(faqs)):
            a, b = faqs[left], faqs[right]
            title_similarity = SequenceMatcher(None, normalized(a["title"]), normalized(b["title"])).ratio()
            body_similarity = SequenceMatcher(None, normalized(a["content"]), normalized(b["content"])).ratio()
            distance = hamming(int(a["simhash"], 16), int(b["simhash"], 16))
            exact = a["normalized_content_hash"] == b["normalized_content_hash"]
            if exact or body_similarity >= 0.88 or distance <= 3 or (title_similarity >= 0.90 and body_similarity >= 0.75):
                edges.append({
                    "left_id": a["document_id"], "right_id": b["document_id"], "exact": exact,
                    "title_similarity": round(title_similarity, 4), "body_similarity": round(body_similarity, 4),
                    "simhash_distance": distance, "product_model_difference": sorted(set(a["device_models"]) ^ set(b["device_models"])),
                    "language_difference": a["language"] != b["language"], "source_urls": [a["source_url"], b["source_url"]],
                    "section_locators": [a["section_locator"], b["section_locator"]],
                    "merge_suggestion": "retain_one_content_and_merge_applicable_device_models" if (exact or body_similarity >= 0.88) else "manual_compare_before_merge",
                })
    parent = list(range(len(faqs)))
    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value
    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root
    index_by_id = {item["document_id"]: index for index, item in enumerate(faqs)}
    for edge in edges:
        union(index_by_id[edge["left_id"]], index_by_id[edge["right_id"]])
    groups: dict[int, list[str]] = defaultdict(list)
    for index, item in enumerate(faqs):
        groups[find(index)].append(item["document_id"])
    duplicate_groups = [members for members in groups.values() if len(members) > 1]
    public_records = [{key: value for key, value in item.items() if key != "content"} for item in faqs]
    return {
        "generated_at": now_iso(), "faq_total": len(faqs), "unique_groups": len(groups),
        "duplicate_group_count": len(duplicate_groups), "merge_candidate_pairs": len(edges),
        "records": public_records, "duplicate_groups": duplicate_groups, "pair_evidence": edges,
        "database_modified": False,
    }


def find_excerpt(value: str, chunks: list[KnowledgeChunk]) -> tuple[str, dict, str]:
    needle = normalized(value)
    chosen = next((chunk for chunk in chunks if needle and needle in normalized(chunk.content)), chunks[0] if chunks else None)
    if chosen is None:
        return "", {}, ""
    return " ".join((chosen.content or "").split())[:240], (chosen.metadata_json or {}).get("source_locator") or {}, str(chosen.id)


def alarm_samples(documents: list[KnowledgeDocument], chunks_by_document: dict[str, list[KnowledgeChunk]]) -> list[dict]:
    explicit, named, troubleshooting, safety = [], [], [], []
    seen = {"explicit_alarm": set(), "named_alarm": set(), "troubleshooting_step": set(), "safety_action": set()}
    for document in documents:
        chunks = chunks_by_document[str(document.id)]
        metadata = document.metadata_json or {}
        alarm = metadata.get("alarm_knowledge") or {}
        models = metadata.get("device_models") or ([document.model] if document.model else [])
        for extraction_type, source_items, target in (
            ("explicit_alarm", alarm.get("explicit_alarm_codes") or [], explicit),
            ("named_alarm", alarm.get("named_alarms") or [], named),
        ):
            for item in source_items:
                item_data = item if isinstance(item, dict) else {}
                value = str(
                    item_data.get("alarm_identifier") or item_data.get("alarm_code") or
                    item_data.get("code") or item_data.get("alarm_name") or
                    (item if isinstance(item, (str, int)) else "")
                ).strip()
                key = normalized(value)
                if not key or key in seen[extraction_type]:
                    continue
                seen[extraction_type].add(key)
                excerpt, fallback_locator, chunk_id = find_excerpt(value, chunks)
                target.append({
                    "document_id": str(document.id), "chunk_id": chunk_id,
                    "source_locator": item_data.get("source_locator") or fallback_locator,
                    "extracted_value": value, "source_excerpt": excerpt, "device_model": models,
                    "extraction_type": extraction_type, "review_result": "", "notes": "",
                })
        for chunk in chunks:
            lines = [line.strip() for line in re.split(r"(?<=[。！？.!?;；])\s*|\n+", chunk.content or "") if 12 <= len(line.strip()) <= 400]
            for line in lines:
                normalized_line = normalized(line)
                if re.search(r"(?i)\b(check|ensure|verify|inspect|replace|restart|reset|confirm)\b|检查|确认|更换|复位|重启|排查", line):
                    if normalized_line not in seen["troubleshooting_step"]:
                        seen["troubleshooting_step"].add(normalized_line)
                        troubleshooting.append({
                            "document_id": str(document.id), "chunk_id": str(chunk.id),
                            "source_locator": (chunk.metadata_json or {}).get("source_locator") or {},
                            "extracted_value": line[:180], "source_excerpt": " ".join((chunk.content or "").split())[:240],
                            "device_model": models, "extraction_type": "troubleshooting_step", "review_result": "", "notes": "",
                        })
                if re.search(r"(?i)\b(danger|warning|caution|must|do not|electric shock|disconnect|power off)\b|危险|警告|必须|禁止|断电|防护", line):
                    if normalized_line not in seen["safety_action"]:
                        seen["safety_action"].add(normalized_line)
                        safety.append({
                            "document_id": str(document.id), "chunk_id": str(chunk.id),
                            "source_locator": (chunk.metadata_json or {}).get("source_locator") or {},
                            "extracted_value": line[:180], "source_excerpt": " ".join((chunk.content or "").split())[:240],
                            "device_model": models, "extraction_type": "safety_action", "review_result": "", "notes": "",
                        })
    def deterministic(items: list[dict], count: int) -> list[dict]:
        return sorted(items, key=lambda item: hashlib.sha256((item["document_id"] + item["extracted_value"]).encode("utf-8")).hexdigest())[:count]
    samples = deterministic(explicit, 15) + deterministic(named, 20) + deterministic(troubleshooting, 20) + deterministic(safety, 20)
    if len(deterministic(explicit, 15)) < 15 or len(deterministic(named, 20)) < 20 or len(deterministic(troubleshooting, 20)) < 20 or len(deterministic(safety, 20)) < 20:
        raise RuntimeError("insufficient alarm manual-review sample candidates")
    return samples


def benchmark_gap_fill(session: SessionLocal) -> dict:
    original = list(session.scalars(select(RetrievalEvaluationCase).where(
        RetrievalEvaluationCase.name.like("Task25BR2U2_%") | RetrievalEvaluationCase.name.like("Task25BR2U3_%")
    )))
    original_no_answer = sum(bool((item.metadata_json or {}).get("no_answer")) for item in original)
    original_hard_negative = sum(bool((item.metadata_json or {}).get("hard_negative")) for item in original)
    records = []
    for index, query in enumerate(NO_ANSWER_QUERIES, 1):
        name = f"Task25BR2U3R1_NoAnswer_{index:03d}"
        records.append({
            "case_id": f"candidate:{hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]}",
            "name": name, "category": "no_answer", "query_text": query,
            "query_text_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "expected_document_ids": [], "expected_chunk_ids": [], "conflict_reason": None,
            "review_status": "engineering_candidate", "persisted_to_database": False,
        })
    for index, (query, reason) in enumerate(HARD_NEGATIVE_QUERIES, 1):
        name = f"Task25BR2U3R1_HardNegative_{index:03d}"
        records.append({
            "case_id": f"candidate:{hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]}",
            "name": name, "category": "hard_negative", "query_text": query,
            "query_text_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "expected_document_ids": [], "expected_chunk_ids": [], "conflict_reason": reason,
            "review_status": "engineering_candidate", "persisted_to_database": False,
        })
    return {
        "generated_at": now_iso(), "original_target_candidates": len(original),
        "original_no_answer": original_no_answer, "original_hard_negatives": original_hard_negative,
        "added_no_answer": len(NO_ANSWER_QUERIES), "added_hard_negatives": len(HARD_NEGATIVE_QUERIES),
        "created_this_run": len(records), "skipped_idempotent": 0,
        "review_status": "engineering_candidate", "expert_verified_written": 0,
        "database_constraint_note": "engineering_candidate is not an allowed persisted review_status; candidates remain review artifacts",
        "records": records,
    }


def render_report(summary: dict, rows: list[dict], smartlogger: dict, faq: dict, alarm_counts: Counter, benchmark: dict, first_batch: list[dict]) -> None:
    approve = [item for item in rows if item["decision"] == "RECOMMEND_APPROVE"]
    individual = [item for item in rows if item["decision"] == "REQUIRE_INDIVIDUAL_REVIEW"]
    blocked = [item for item in rows if item["decision"] not in {"RECOMMEND_APPROVE", "REQUIRE_INDIVIDUAL_REVIEW"}]
    def lines(items: list[dict]) -> str:
        return "\n".join(f"- `{item['document_id']}` — {item['masked_title']} — {item['decision']}" for item in items) or "- 无"
    REPORT.write_text(f"""# Task 25B-R2-U3-R1 正式文档批准前质量审计

## 结论

本次只生成审核建议和 `engineering_candidate` Benchmark 缺口候选，没有批准文档、写入 expert review、调用 Embedding/DashVector 或执行 Pilot 索引。审计对象为 34 份数据库 pending 官方文档及 5 份仅检查的 `NEEDS_METADATA` 候选；1,161 个数据库 Chunk 全部纳入统计。

## A. 推荐优先批准

{lines(approve)}

## B. 必须逐份审核

{lines(individual)}

## C. 当前不得批准

{lines(blocked)}

## SmartLogger 专项

- 文档：{len(smartlogger['documents'])}；Chunk：{smartlogger['combined_chunks']}。
- 两份长文档均保持 `REQUIRE_INDIVIDUAL_REVIEW`，即使自动阈值通过也不得批量批准。
- 每份已使用文档 ID 派生的固定种子随机抽取 20 个不重复 Chunk，人工结果列保持空白。
{chr(10).join(f"- `{item['document_id']}`：exact={item['exact_duplicate_ratio']:.2%}，near={item['near_duplicate_ratio']:.2%}，locator={item['source_locator_coverage']:.2%}，表格样式 Chunk={item['table_chunk_count']}，重复页眉候选={item['repeated_header_count']}，阈值通过={item['thresholds_passed']}。" for item in smartlogger['documents'])}

## FAQ 重复检查

- FAQ 候选：{faq['faq_total']}；独立组：{faq['unique_groups']}；重复/近重复组：{faq['duplicate_group_count']}；合并候选对：{faq['merge_candidate_pairs']}。
- 仅生成 `applicable_device_models` 合并建议，没有修改文档或 Chunk。

## 告警人工抽样

- 显式告警：{alarm_counts['explicit_alarm']}；命名告警：{alarm_counts['named_alarm']}；排障步骤：{alarm_counts['troubleshooting_step']}；安全动作：{alarm_counts['safety_action']}。
- 所有 `review_result` 和 `notes` 均为空，等待人工核验。

## Benchmark 缺口

- 原 no-answer={benchmark['original_no_answer']}，补充={benchmark['added_no_answer']}。
- 原 hard-negative={benchmark['original_hard_negatives']}，补充={benchmark['added_hard_negatives']}。
- 新候选状态只为 `engineering_candidate`，expected IDs 均为空，expert_verified 写入为 0。

## 推荐人工审核顺序

第一批只批准以下 3 份代表性文档：

{lines(first_batch)}

随后运行：

```powershell
cd "D:\\Work Space\\Energy-Maintenance\\backend"
uv run python scripts\\check_task25b_r2_u3_corpus_gate.py --resume-after-document-approval
```

确认 active Chunk、状态过滤和引用正常后，再逐份处理两份 SmartLogger 长文档。达到 300 active Chunk 后先暂停扩充并复核门禁，不要求一次批准全部 34 份。

审核页面：http://127.0.0.1:8012/review

## 汇总

- 推荐批准：{summary['decision_counts'].get('RECOMMEND_APPROVE', 0)}。
- 必须逐份审核：{summary['decision_counts'].get('REQUIRE_INDIVIDUAL_REVIEW', 0)}。
- NEEDS_METADATA：{summary['decision_counts'].get('NEEDS_METADATA', 0)}。
- projected chunks：{summary['projected_chunks']}。
- exact duplicate chunks：{summary['exact_duplicate_chunks']}；near duplicate chunks：{summary['near_duplicate_chunks']}。
- source locator/page coverage：{summary['locator_or_page_coverage']:.2%}；heading coverage：{summary['heading_coverage']:.2%}。
""", encoding="utf-8")


def main() -> int:
    quality = json.loads((U3_RUNTIME / "u3_corpus_quality.json").read_text(encoding="utf-8"))
    internal = json.loads((U3_RUNTIME / "huawei_support_html_internal.json").read_text(encoding="utf-8"))
    with SessionLocal() as session:
        documents = list(session.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.manufacturer == "huawei",
            KnowledgeDocument.source_type.in_(["vendor_official", "vendor_official_html"]),
            KnowledgeDocument.review_status == "pending_review",
        ).order_by(KnowledgeDocument.created_at, KnowledgeDocument.id)))
        chunks = list(session.scalars(select(KnowledgeChunk).where(
            KnowledgeChunk.document_id.in_([item.id for item in documents]),
            KnowledgeChunk.status == "active",
        ).order_by(KnowledgeChunk.document_id, KnowledgeChunk.chunk_index)))
        chunks_by_document: dict[str, list[KnowledgeChunk]] = defaultdict(list)
        for chunk in chunks:
            chunks_by_document[str(chunk.document_id)].append(chunk)
        before = {
            "captured_at": now_iso(), "pending_documents": len(documents), "projected_chunks": len(chunks),
            "approved_documents": sum(item.review_status == "approved" for item in documents),
            "expert_verified": int(session.query(RetrievalEvaluationCase).filter(RetrievalEvaluationCase.review_status == "expert_verified").count()),
        }
        write_json("preapproval_baseline.json", before)
        if len(documents) != 34 or len(chunks) != 1161 or before["approved_documents"] != 0:
            raise RuntimeError(f"U3 boundary drift: {before}")
        rows = [document_row(document, chunks_by_document[str(document.id)]) for document in documents]
        rows.extend(needs_metadata_rows(quality.get("records") or [], internal.get("records") or []))
        rows_by_id = {item["document_id"]: item for item in rows}
        id_by_key = {
            ((document.metadata_json or {}).get("content_hash") or "", document.source or ""): str(document.id)
            for document in documents
        }
        smartlogger = smartlogger_audit(documents, chunks_by_document, rows_by_id)
        faq = faq_duplicate_audit(quality.get("records") or [], internal.get("records") or [], id_by_key)
        samples = alarm_samples(documents, chunks_by_document)
        alarm_counts = Counter(item["extraction_type"] for item in samples)
        benchmark = benchmark_gap_fill(session)
        decision_counts = Counter(item["decision"] for item in rows)
        noise_chunks = sum(item["navigation_noise_count"] + item["footer_noise_count"] + item["encoding_issue_count"] for item in rows)
        total_chunks = sum(item["chunk_count"] for item in rows)
        global_exact, global_near, _ = duplicate_metrics(chunks)
        summary = {
            "generated_at": now_iso(), "database_pending_documents": len(documents),
            "inspection_only_needs_metadata": decision_counts["NEEDS_METADATA"], "audited_entries": len(rows),
            "projected_chunks": total_chunks, "decision_counts": dict(decision_counts),
            "exact_duplicate_chunks": global_exact,
            "near_duplicate_chunks": global_near,
            "noise_chunks": noise_chunks,
            "locator_or_page_coverage": round(sum(max(item["source_locator_coverage"], item["page_number_coverage"]) * item["chunk_count"] for item in rows) / total_chunks, 4),
            "heading_coverage": round(sum(item["heading_path_coverage"] * item["chunk_count"] for item in rows) / total_chunks, 4),
            "documents_approved": 0, "expert_reviews_written": 0, "pilot_indexed": 0,
        }
        checklist_payload = {"summary": summary, "documents": rows}
        write_json("document_approval_checklist.json", checklist_payload)
        write_csv("document_approval_checklist.csv", CHECKLIST_FIELDS, rows)
        write_json("smartlogger_chunk_audit.json", smartlogger)
        write_json("faq_duplicate_groups.json", faq)
        write_csv("alarm_manual_review_sample.csv", [
            "document_id", "chunk_id", "source_locator", "extracted_value", "source_excerpt",
            "device_model", "extraction_type", "review_result", "notes",
        ], samples)
        write_json("benchmark_gap_fill.json", benchmark)
        preferred_families = ["SUN2000-(3KTL-10KTL)-M1 User Manual", "SUN2000-(5K-12K)-MAP0 Series User Manual", "HUAWEI LUNA2000-(107-241)"]
        recommended = [item for item in rows if item["decision"] == "RECOMMEND_APPROVE"]
        first_batch = []
        for needle in preferred_families:
            candidate = next((item for item in recommended if needle in item["masked_title"]), None)
            if candidate and candidate not in first_batch:
                first_batch.append(candidate)
        for item in recommended:
            if len(first_batch) >= 3:
                break
            if item not in first_batch:
                first_batch.append(item)
        render_report(summary, rows, smartlogger, faq, alarm_counts, benchmark, first_batch[:3])
        after_approved = int(session.query(KnowledgeDocument).filter(
            KnowledgeDocument.manufacturer == "huawei",
            KnowledgeDocument.source_type.in_(["vendor_official", "vendor_official_html"]),
            KnowledgeDocument.review_status == "approved",
        ).count())
        after_expert = int(session.query(RetrievalEvaluationCase).filter(RetrievalEvaluationCase.review_status == "expert_verified").count())
        if after_approved != 0 or after_expert != before["expert_verified"]:
            raise RuntimeError("forbidden approval or expert-review drift detected")
    print(json.dumps({"status": "PASSED", **summary, "alarm_samples": dict(alarm_counts), "benchmark": {key: benchmark[key] for key in ("original_no_answer", "added_no_answer", "original_hard_negatives", "added_hard_negatives")}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
