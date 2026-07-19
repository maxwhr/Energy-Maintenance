from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from lxml import html
from lxml import etree

from task25b_r2_u3_common import RUNTIME, is_official_url, now_iso, write_csv, write_json

from app.services.alarm_knowledge_extraction_service import AlarmKnowledgeExtractionService
from app.services.equipment_classification_service import EquipmentClassificationService


SEEDS = [
    "https://solar.huawei.com/cn/products/SUN2000-150K-MG0-ZH/support/",
    "https://solar.huawei.com/cn/products/SUN2000-15-17-20-25K-MB0-ZH/support/",
    "https://solar.huawei.com/cn/products/SUN2000-5-12K-MAP0-ZH/support/",
    "https://solar.huawei.com/cn/products/LUNA2000-7-14-21-S1/support/",
    "https://solar.huawei.com/cn/products/HUAWEI-SmartGuard/support/",
    "https://solar.huawei.com/en/products/sun2000-150k-mg0/support/",
    "https://solar.huawei.com/en/products/SUN2000-5-12K-MAP0/support/",
    "https://solar.huawei.com/en/products/SUN2000-12-15-17-20-25K-MB0/support/",
    "https://solar.huawei.com/en/products/sun2000-3-4-5-6-8-10ktl-m1/support/",
    "https://solar.huawei.com/en/products/SUN2000-3-4-5-6KTL-L1/support/",
    "https://solar.huawei.com/en/products/sun2000-330ktl-h1-h2/support/",
    "https://solar.huawei.com/en/products/luna2000-5-10-15-s0/support/",
    "https://solar.huawei.com/en/products/LUNA2000-7-14-21-S1/support/",
    "https://solar.huawei.com/en/products/LUNA2000-97-129-161-200kwh/support/",
    "https://solar.huawei.com/ie/products/luna2000-215-series/support",
    "https://solar.huawei.com/ie/products/huawei-smartguard/support",
    "https://solar.huawei.com/en/products/merc-600w-pa0/support/",
]

PUBLIC_SUPPORT_DOCUMENTS = [
    {"nid": "EDOC1100330465", "family": "SmartLogger", "type": "ALARM_REFERENCE", "categories": ["data_logger", "plant_controller"], "topic_mode": "alarm"},
    {"nid": "EDOC1100108365", "family": "SmartLogger", "type": "USER_MANUAL", "categories": ["data_logger", "communication_device", "plant_controller"], "topic_mode": "service"},
    {"nid": "EDOC1100358764", "family": "FusionSolar", "type": "FUSIONSOLAR_OPERATION_GUIDE", "categories": ["management_platform"], "topic_mode": "service"},
    {"nid": "EDOC1100394512", "family": "LUNA2000", "type": "USER_MANUAL", "categories": ["energy_storage", "data_logger"], "topic_mode": "service"},
    {"nid": "EDOC1100366802", "family": "SUN2000", "type": "USER_MANUAL", "categories": ["pv_inverter", "power_optimizer"], "topic_mode": "service"},
    {"nid": "EDOC1100325389", "family": "SmartGuard", "type": "USER_MANUAL", "categories": ["smart_guard", "communication_device"], "topic_mode": "service"},
    {"nid": "EDOC1100163578", "family": "SUN2000", "type": "USER_MANUAL", "categories": ["pv_inverter", "communication_device"], "topic_mode": "service"},
    {"nid": "EDOC1100341318", "family": "SUN2000", "type": "USER_MANUAL", "categories": ["pv_inverter"], "topic_mode": "service"},
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Energy-Maintenance-Huawei-Support-Knowledge/1.0 (public; no-auth)"
FAQ_MARKERS = {"faq", "faqs", "常见问题", "常见问题解答", "preguntas más frecuentes"}
OPERATION_TERMS = re.compile(
    r"(?i)(?:step\s*\d+|步骤|check|replace|reset|fault|alarm|fails?|unable|warning|power off|"
    r"检查|更换|重置|告警|故障|异常|断电|安全|通信|password|wifi|ground|insulation|fuse|battery)"
)
MODEL_PATTERN = re.compile(r"(?:SUN2000|LUNA2000|MERC|SmartGuard|SmartLogger|SmartPVMS|SmartACU)[A-Za-z0-9/().-]*", re.I)
SERVICE_TOPIC = re.compile(
    r"(?i)(?:alarm|fault|troubleshoot|maintenance|replace|replacement|install|commission|power.off|"
    r"communication|wifi|wlan|rs485|battery|safety|ground|insulation|afci|indicator|upgrade|login|password|"
    r"告警|故障|维护|更换|安装|调测|断电|通信|安全|接地|绝缘|指示灯|密码)"
)
ALARM_TOPIC = re.compile(r"^\s*(?:\d{3,6}|[A-Z]{1,5}[-_]\d{2,6})\s+", re.I)


def clean_text(node) -> str:
    return " ".join(node.text_content().split())


def product_family(text: str) -> str:
    lowered = text.lower()
    for token, family in (
        ("sun2000", "SUN2000"), ("luna2000", "LUNA2000"), ("merc", "MERC"),
        ("smartguard", "SmartGuard"), ("smartlogger", "SmartLogger"),
        ("smartpvms", "FusionSolar"), ("fusionsolar", "FusionSolar"),
    ):
        if token in lowered:
            return family
    return "Huawei Smart PV"


def allowed_by_robots(client: httpx.Client, url: str, cache: dict[str, RobotFileParser | None]) -> bool:
    host = urlparse(url).hostname or ""
    if host not in cache:
        robots_url = f"https://{host}/robots.txt"
        try:
            response = client.get(robots_url)
            parser = RobotFileParser(robots_url)
            parser.parse(response.text.splitlines() if response.status_code == 200 else [])
            cache[host] = parser
        except Exception:
            cache[host] = None
    parser = cache[host]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def extract_faqs(page_url: str, body: bytes) -> tuple[str, list[dict]]:
    root = html.fromstring(body)
    title = clean_text(root.xpath("//title")[0]) if root.xpath("//title") else page_url
    records: list[dict] = []
    answer_items = root.xpath(
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' right_answer ')]//li[.//h3]"
    )
    for item in answer_items:
        headings = item.xpath(".//h3[1]")
        if not headings:
            continue
        question = clean_text(headings[0])
        parts = []
        for node in item.xpath(".//p|.//ol/li|.//ul/li"):
            value = clean_text(node)
            if value and value.lower() not in {"click to view >", "点击查看 >", "click to view", "点击查看"}:
                parts.append(value)
        content = "\n".join(dict.fromkeys(parts)).strip()
        if question and len(content) >= 50 and OPERATION_TERMS.search(question + " " + content):
            records.append({"question_title": question[:255], "content": content})
    if records:
        return title, records
    for selector in ("//script", "//style", "//noscript", "//header", "//footer", "//nav"):
        for node in root.xpath(selector):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    ordered = root.xpath("//h2|//h3|//h4|//h5|//p|//li")
    in_faq = False
    current_title: str | None = None
    current_parts: list[str] = []
    records = []

    def flush() -> None:
        nonlocal current_title, current_parts
        content = "\n".join(dict.fromkeys(item for item in current_parts if item)).strip()
        if current_title and len(content) >= 80 and OPERATION_TERMS.search(current_title + " " + content):
            records.append({"question_title": current_title[:255], "content": content})
        current_title, current_parts = None, []

    for node in ordered:
        text = clean_text(node)
        if not text or len(text) > 4000:
            continue
        tag = node.tag.lower()
        lowered = text.lower().strip(":：")
        if tag in {"h2", "h3", "h4", "h5"} and any(marker == lowered or marker in lowered for marker in FAQ_MARKERS):
            flush()
            in_faq = True
            continue
        if not in_faq:
            continue
        if tag == "h2" and current_title:
            flush()
            if not OPERATION_TERMS.search(text):
                in_faq = False
                continue
        if tag in {"h3", "h4", "h5"}:
            flush()
            current_title = text
        elif current_title and text != current_title:
            current_parts.append(text)
    flush()
    return title, records


def support_api_get(client: httpx.Client, path: str, params: dict, last_request: list[float]) -> httpx.Response:
    delay = 1.0 - (time.monotonic() - last_request[0])
    if delay > 0:
        time.sleep(delay)
    response = client.get(
        "https://support.huawei.com/supportgateway/view/v1/enterprise" + path,
        params=params,
        headers={"Referer": "https://support.huawei.com/enterprise/"},
    )
    last_request[0] = time.monotonic()
    return response


def html_topic_text(body: bytes) -> str:
    root = html.fromstring(body)
    for node in root.xpath("//script|//style|//noscript"):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    parts = []
    for node in root.xpath("//h1|//h2|//h3|//h4|//p|//li|//tr"):
        text = clean_text(node)
        if not text or text in parts[-3:]:
            continue
        if node.tag.lower() in {"h1", "h2", "h3", "h4"}:
            parts.append("## " + text)
        else:
            parts.append(text)
    return "\n\n".join(parts).strip()


def collect_public_support_documents(client: httpx.Client, specs: list[dict] | None = None, max_topics: int = 100) -> tuple[list[dict], list[dict]]:
    records = []
    results = []
    last_request = [0.0]
    extractor = AlarmKnowledgeExtractionService()
    for spec in specs or PUBLIC_SUPPORT_DOCUMENTS:
        nid = spec["nid"]
        try:
            basic_response = support_api_get(client, "/doc/basic", {"nid": nid}, last_request)
            catalogue_response = support_api_get(client, "/doc/catalogue", {"nid": nid}, last_request)
            if basic_response.status_code in {401, 403} or catalogue_response.status_code in {401, 403}:
                results.append({"nid": nid, "status": "BLOCKED_ACCESS"})
                continue
            basic = basic_response.json()
            if basic.get("code") != "support-view-000000" or catalogue_response.status_code != 200:
                results.append({"nid": nid, "status": "INVALID", "basic_code": basic.get("code")})
                continue
            data = basic.get("data") or {}
            catalogue = etree.fromstring(catalogue_response.content)
            topic_nodes = catalogue.xpath(".//file[@partNo]")
            selected = []
            for node in topic_nodes:
                topic_title = (node.get("txtName") or node.get("name") or "").strip()
                if spec["topic_mode"] == "alarm":
                    include = bool(ALARM_TOPIC.search(topic_title))
                else:
                    include = bool(SERVICE_TOPIC.search(topic_title))
                if include:
                    selected.append({"part_no": node.get("partNo"), "title": topic_title, "topic_id": node.get("topicId")})
            selected = selected[:max_topics]
            sections = []
            for topic in selected:
                response = support_api_get(client, "/doc/main-content", {"nid": nid, "partNo": topic["part_no"]}, last_request)
                if response.status_code in {401, 403}:
                    continue
                if response.status_code != 200 or b"<html" not in response.content[:1000].lower():
                    continue
                text = html_topic_text(response.content)
                if len(text) < 80:
                    continue
                sections.append({**topic, "content": text, "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()})
            if not sections:
                results.append({"nid": nid, "status": "NO_RELEVANT_PUBLIC_TOPICS", "selected": len(selected)})
                continue
            source_url = f"https://support.huawei.com/enterprise/en/doc/{nid}"
            combined = "\n\n".join(f"# {item['title']}\n\n{item['content']}" for item in sections)
            title = data.get("title") or nid
            models = sorted(set(MODEL_PATTERN.findall((data.get("keywords") or "") + " " + title)))
            locators = [
                {"source_url": source_url, "nid": nid, "part_no": item["part_no"], "topic_id": item["topic_id"], "section_title": item["title"]}
                for item in sections
            ]
            alarm = extractor.extract(title=title, text=combined, device_models=models, source_locator={"source_url": source_url, "nid": nid})
            records.append({
                "source_provenance": "VENDOR_OFFICIAL", "official_source": True,
                "issuer": "Huawei Technologies Co., Ltd.", "rights_basis": "vendor_public",
                "source_url": source_url, "source_page_url": source_url, "page_title": title,
                "question_title": title, "content": combined,
                "page_content_hash": hashlib.sha256(catalogue_response.content).hexdigest(),
                "content_hash": hashlib.sha256(combined.encode("utf-8")).hexdigest(),
                "product_family": spec["family"], "device_models": models,
                "equipment_categories": spec["categories"], "document_type": spec["type"],
                "language": "en", "section_locator": {"source_url": source_url, "nid": nid, "section_count": len(locators)},
                "section_locators": locators, "alarm_knowledge": alarm,
                "collected_at": now_iso(), "quality_status": "READY_FOR_HUMAN_REVIEW",
                "review_status": "pending_review", "approved_for_pilot": False,
            })
            results.append({"nid": nid, "status": "COLLECTED", "title": title, "catalogue_topics": len(topic_nodes), "selected_topics": len(selected), "collected_topics": len(sections), "content_length": len(combined)})
        except Exception as exc:
            results.append({"nid": nid, "status": "BLOCKED_ACCESS", "reason": type(exc).__name__})
    return records, results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--support-nid")
    parser.add_argument("--max-topics", type=int, default=100)
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    client = httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"},
        follow_redirects=True, timeout=30, limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    robots: dict[str, RobotFileParser | None] = {}
    extractor = AlarmKnowledgeExtractionService()
    if args.support_nid:
        specs = [item for item in PUBLIC_SUPPORT_DOCUMENTS if item["nid"] == args.support_nid]
        if not specs:
            raise SystemExit("unknown support nid")
        support_records, support_results = collect_public_support_documents(client, specs, max(1, min(100, args.max_topics)))
        internal_path = RUNTIME / f"support_doc_{args.support_nid}_internal.json"
        internal_path.write_text(json.dumps({"generated_at": now_iso(), "records": support_records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload = {"generated_at": now_iso(), "nid": args.support_nid, "documents": len(support_records), "results": support_results, "access_control_bypassed": False}
        write_json(f"support_doc_{args.support_nid}.json", payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if support_records else 2
    if args.merge:
        base_path = RUNTIME / "huawei_support_html_internal.json"
        base = json.loads(base_path.read_text(encoding="utf-8")) if base_path.exists() else {"records": []}
        records = [item for item in base.get("records", []) if item.get("document_type") == "FAQ_TROUBLESHOOTING"]
        support_results = []
        for spec in PUBLIC_SUPPORT_DOCUMENTS:
            path = RUNTIME / f"support_doc_{spec['nid']}_internal.json"
            if not path.exists():
                support_results.append({"nid": spec["nid"], "status": "MISSING"})
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            records.extend(data.get("records", []))
            support_results.append({"nid": spec["nid"], "status": "MERGED", "documents": len(data.get("records", []))})
        unique = {item["content_hash"]: item for item in records}
        records = list(unique.values())
        base_path.write_text(json.dumps({"generated_at": now_iso(), "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_records = [{k: v for k, v in item.items() if k != "content"} | {"content_length": len(item["content"])} for item in records]
        payload = {
            "generated_at": now_iso(), "pages_scanned": len(SEEDS),
            "html_faq_documents": sum(item.get("document_type") == "FAQ_TROUBLESHOOTING" for item in records),
            "public_support_documents": sum(item.get("document_type") != "FAQ_TROUBLESHOOTING" for item in records),
            "total_candidate_documents": len(records), "public_support_results": support_results,
            "explicit_alarm_codes": len({code for item in records for code in item["alarm_knowledge"]["explicit_alarm_codes"]}),
            "named_alarms": sum(len(item["alarm_knowledge"]["named_alarms"]) for item in records),
            "fault_symptoms": sum(len(item["alarm_knowledge"]["fault_symptoms"]) for item in records),
            "troubleshooting_steps": sum(item["alarm_knowledge"]["troubleshooting_steps"] for item in records),
            "safety_actions": sum(item["alarm_knowledge"]["safety_actions"] for item in records),
            "access_control_bypassed": False, "automatic_approval": False, "records": summary_records,
        }
        write_json("huawei_support_html_knowledge.json", payload)
        print(json.dumps({k: payload[k] for k in ("html_faq_documents", "public_support_documents", "total_candidate_documents", "explicit_alarm_codes", "named_alarms", "troubleshooting_steps", "safety_actions")}, ensure_ascii=False))
        return 0
    records: list[dict] = []
    pages: list[dict] = []
    last_request = 0.0
    for seed in SEEDS:
        delay = 1.0 - (time.monotonic() - last_request)
        if delay > 0:
            time.sleep(delay)
        if not is_official_url(seed) or not allowed_by_robots(client, seed, robots):
            pages.append({"source_url": seed, "status": "BLOCKED_ACCESS", "reason": "domain_or_robots"})
            continue
        try:
            response = client.get(seed)
            last_request = time.monotonic()
        except Exception as exc:
            pages.append({"source_url": seed, "status": "BLOCKED_ACCESS", "reason": type(exc).__name__})
            continue
        final_url = str(response.url)
        if response.status_code in {401, 403} or not is_official_url(final_url):
            pages.append({"source_url": seed, "final_url": final_url, "status": "BLOCKED_ACCESS", "http_status": response.status_code})
            continue
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            pages.append({"source_url": seed, "final_url": final_url, "status": "INVALID", "http_status": response.status_code})
            continue
        page_title, faqs = extract_faqs(final_url, response.content)
        page_hash = hashlib.sha256(response.content).hexdigest()
        models = sorted(set(MODEL_PATTERN.findall(page_title + " " + final_url)))
        family = product_family(page_title + " " + final_url)
        categories = EquipmentClassificationService.classify(page_title, family, models)
        accepted = 0
        for index, faq in enumerate(faqs):
            section_locator = {"source_url": final_url, "question_title": faq["question_title"], "section_index": index}
            extraction = extractor.extract(
                title=faq["question_title"], text=faq["content"], device_models=models,
                source_locator=section_locator,
            )
            content_hash = hashlib.sha256((faq["question_title"] + "\n" + faq["content"]).encode("utf-8")).hexdigest()
            records.append({
                "source_provenance": "VENDOR_OFFICIAL", "official_source": True,
                "issuer": "Huawei Technologies Co., Ltd.", "rights_basis": "vendor_public",
                "source_url": final_url, "source_page_url": final_url, "page_title": page_title,
                "question_title": faq["question_title"], "content": faq["content"],
                "page_content_hash": page_hash, "content_hash": content_hash,
                "product_family": family, "device_models": models, "equipment_categories": categories,
                "document_type": "FAQ_TROUBLESHOOTING", "language": "zh" if "/cn/" in final_url else "en",
                "section_locator": section_locator, "alarm_knowledge": extraction,
                "collected_at": now_iso(), "quality_status": "READY_FOR_HUMAN_REVIEW",
                "review_status": "pending_review", "approved_for_pilot": False,
            })
            accepted += 1
        pages.append({"source_url": seed, "final_url": final_url, "status": "COLLECTED", "http_status": response.status_code, "faq_documents": accepted, "page_content_hash": page_hash})
    support_records, support_results = collect_public_support_documents(client)
    records.extend(support_records)
    unique: dict[str, dict] = {}
    for item in records:
        unique.setdefault(item["content_hash"], item)
    records = list(unique.values())
    internal = RUNTIME / "huawei_support_html_internal.json"
    internal.write_text(json.dumps({"generated_at": now_iso(), "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_records = [{k: v for k, v in item.items() if k != "content"} | {"content_length": len(item["content"])} for item in records]
    payload = {
        "generated_at": now_iso(), "pages_scanned": len(SEEDS),
        "pages_collected": sum(item.get("status") == "COLLECTED" for item in pages),
        "blocked_access": sum(item.get("status") == "BLOCKED_ACCESS" for item in pages),
        "html_faq_documents": len(records), "duplicate_sections_removed": len(unique) - len(records),
        "public_support_documents": len(support_records), "public_support_results": support_results,
        "access_control_bypassed": False, "automatic_approval": False,
        "explicit_alarm_codes": len({code for item in records for code in item["alarm_knowledge"]["explicit_alarm_codes"]}),
        "named_alarms": sum(len(item["alarm_knowledge"]["named_alarms"]) for item in records),
        "fault_symptoms": sum(len(item["alarm_knowledge"]["fault_symptoms"]) for item in records),
        "troubleshooting_steps": sum(item["alarm_knowledge"]["troubleshooting_steps"] for item in records),
        "safety_actions": sum(item["alarm_knowledge"]["safety_actions"] for item in records),
        "pages": pages, "records": summary_records,
    }
    write_json("huawei_support_html_knowledge.json", payload)
    write_csv("huawei_support_html_knowledge.csv", [
        "source_url", "page_title", "question_title", "product_family", "device_models",
        "equipment_categories", "language", "content_hash", "content_length", "quality_status", "collected_at",
    ], summary_records)
    print(json.dumps({k: payload[k] for k in ("pages_scanned", "pages_collected", "blocked_access", "html_faq_documents", "explicit_alarm_codes", "named_alarms", "fault_symptoms", "troubleshooting_steps", "safety_actions")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
