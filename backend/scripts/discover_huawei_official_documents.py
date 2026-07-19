from __future__ import annotations

import argparse
import json
import re
import time
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

from task25b_r2_u2_common import OFFICIAL_DOMAINS, now_iso, is_official_url, write_csv, write_json


START_URLS = [
    "https://solar.huawei.com/en/downloadcenter/",
    "https://solar.huawei.com/en/products/SUN2000-5-12K-MAP0/support/",
    "https://solar.huawei.com/en/products/SUN2000-12-15-17-20-25K-MB0/support/",
    "https://solar.huawei.com/ie/products/sun2000-150k-mg0/support/",
    "https://solar.huawei.com/ie/products/LUNA2000-7-14-21-S1/support/",
    "https://solar.huawei.com/es/products/LUNA2000-215-Series/support/",
    "https://solar.huawei.com/en/products/HUAWEI-SmartGuard/",
    "https://solar.huawei.com/en/products/MERC-1100-1300-P/",
]

PUBLIC_DOCUMENT_SEEDS = [
    ("https://solar.huawei.com/-/media/Solar/attachment/pdf/eu/service/download/USB-Adapter2000%20User%20Manual.pdf", "USB-Adapter2000 User Manual"),
    ("https://solar.huawei.com/-/media/Solar/attachment/pdf/au/service/commercial/SUN2000-20-40KTL-M3-QuickGuide.pdf", "SUN2000-20-40KTL-M3 Quick Guide"),
    ("https://solar.huawei.com/-/media/SolarV3/downloadcenter/accessories/SmartLogger/SmartLogger3000%20Quick%20Guide.pdf", "SmartLogger3000 Quick Guide"),
    ("https://solar.huawei.com/-/media/SolarV3/downloadcenter/accessories/SmartLogger/SmartLogger3000B%20Quick%20Guide.pdf", "SmartLogger3000B Quick Guide"),
]

USER_AGENT = "Energy-Maintenance-Huawei-Official-Corpus/1.0 (+official-public-documents; no-auth)"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


def canonical(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def product_info(text: str) -> tuple[str, list[str]]:
    models = sorted(set(re.findall(r"(?:SUN2000|LUNA2000|MERC|SmartGuard|SmartLogger)[A-Za-z0-9/().-]*", text, re.I)))
    lowered = text.lower()
    family = next((name for token, name in (
        ("sun2000", "SUN2000"), ("luna2000", "LUNA2000"), ("merc", "MERC"),
        ("smartguard", "SmartGuard"), ("smartlogger", "SmartLogger"), ("fusionsolar", "FusionSolar"),
    ) if token in lowered), "Huawei Smart PV")
    return family, models[:30]


def document_type(text: str) -> str:
    lowered = text.lower()
    for token, value in (
        ("user manual", "USER_MANUAL"), ("maintenance", "MAINTENANCE_GUIDE"),
        ("installation", "INSTALLATION_GUIDE"), ("quick guide", "QUICK_GUIDE"),
        ("alarm", "ALARM_REFERENCE"), ("troubleshoot", "TROUBLESHOOTING_GUIDE"),
        ("replacement", "PART_REPLACEMENT_GUIDE"), ("commission", "COMMISSIONING_GUIDE"),
        ("safety", "SAFETY_GUIDE"), ("communication", "COMMUNICATION_GUIDE"),
        ("datasheet", "DATASHEET"), ("release", "RELEASE_NOTE"),
    ):
        if token in lowered:
            return value
    return "TECHNICAL_DOCUMENT"


def is_document_link(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in (".pdf", ".docx", "download.huawei.com/edownload", "/download?"))


def should_follow(url: str, depth: int) -> bool:
    if depth >= 4 or not is_official_url(url, allow_cdn=False):
        return False
    lowered = url.lower()
    return any(token in lowered for token in ("/support", "/download", "/products/"))


class PoliteClient:
    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document;q=0.9,*/*;q=0.5"},
            timeout=30, follow_redirects=True, limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )
        self.last_request = 0.0
        self.robots: dict[str, RobotFileParser | None] = {}

    def _wait(self):
        delay = 1.0 - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)

    def get(self, url: str, **kwargs) -> httpx.Response:
        self._wait()
        response = self.client.get(url, **kwargs)
        self.last_request = time.monotonic()
        return response

    def allowed(self, url: str) -> bool:
        host = urlparse(url).hostname or ""
        if host not in self.robots:
            robots_url = f"https://{host}/robots.txt"
            try:
                response = self.get(robots_url)
                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(response.text.splitlines() if response.status_code == 200 else [])
                self.robots[host] = parser
            except Exception:
                self.robots[host] = None
        parser = self.robots[host]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)


def probe(client: PoliteClient, url: str) -> dict:
    if not client.allowed(url):
        return {"final_url": url, "status": 0, "blocked": True, "reason": "robots_disallow", "mime": ""}
    try:
        response = client.get(url, headers={"Range": "bytes=0-4095"})
        final_url = str(response.url)
        text = response.text[:4096].lower() if "text" in response.headers.get("content-type", "") else ""
        access = response.status_code in {401, 403} or any(term in text for term in ("captcha", "sign in", "log in", "验证码"))
        return {
            "final_url": final_url, "status": response.status_code, "blocked": access,
            "reason": "access_control" if access else None,
            "mime": response.headers.get("content-type", "").split(";")[0].lower(),
        }
    except Exception as exc:
        return {"final_url": url, "status": 0, "blocked": True, "reason": type(exc).__name__, "mime": ""}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--max-documents", type=int, default=100)
    args = parser.parse_args()
    max_pages = max(1, min(500, args.max_pages))
    max_documents = max(1, min(100, args.max_documents))
    client = PoliteClient()
    queue = deque((url, 0) for url in START_URLS)
    visited: set[str] = set()
    candidates: dict[str, dict] = {}
    pages = 0
    third_party_skipped = 0
    for url, title in PUBLIC_DOCUMENT_SEEDS:
        candidates[canonical(url)] = {"source_url": url, "source_page": "official_public_seed", "document_title": title}

    while queue and pages < max_pages and len(candidates) < max_documents:
        url, depth = queue.popleft()
        url = canonical(url)
        if url in visited or not is_official_url(url, allow_cdn=False):
            continue
        visited.add(url)
        if not client.allowed(url):
            continue
        try:
            response = client.get(url)
        except Exception:
            continue
        pages += 1
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            continue
        parser_html = Links()
        parser_html.feed(response.text)
        for href, text in parser_html.links:
            absolute = canonical(urljoin(str(response.url), href))
            if not absolute.startswith("https://"):
                continue
            if not is_official_url(absolute):
                third_party_skipped += 1
                continue
            if is_document_link(absolute):
                candidates.setdefault(absolute, {"source_url": absolute, "source_page": str(response.url), "document_title": text or absolute.rsplit("/", 1)[-1]})
            elif should_follow(absolute, depth):
                queue.append((absolute, depth + 1))

    records = []
    manual = []
    for base in list(candidates.values())[:max_documents]:
        result = probe(client, base["source_url"])
        title = base["document_title"] or base["source_url"].rsplit("/", 1)[-1]
        family, models = product_info(" ".join((title, base["source_url"], base["source_page"])))
        final = result["final_url"]
        official = is_official_url(final)
        file_type = "pdf" if ("pdf" in result["mime"] or ".pdf" in urlparse(final).path.lower()) else (
            "docx" if ("wordprocessingml" in result["mime"] or ".docx" in urlparse(final).path.lower()) else "html"
        )
        requires_login = bool(result["blocked"] and result["reason"] == "access_control")
        downloadable = bool(official and result["status"] in {200, 206} and not result["blocked"] and file_type in {"pdf", "docx"})
        record = {
            "source_url": base["source_url"], "final_url": final, "official_domain": official,
            "product_family": family, "device_models": models, "document_title": title[:255],
            "document_type": document_type(title + " " + final), "language": "zh" if "/cn/" in final else "en",
            "version": "unspecified", "release_date": None, "file_type": file_type,
            "download_available": downloadable, "requires_login": requires_login,
            "requires_manual_download": bool(not downloadable), "source_page": base["source_page"],
            "http_status": result["status"], "blocked_reason": result["reason"], "discovered_at": now_iso(),
        }
        records.append(record)
        if record["requires_manual_download"]:
            manual.append(record)

    fields = [
        "source_url", "final_url", "official_domain", "product_family", "device_models", "document_title",
        "document_type", "language", "version", "release_date", "file_type", "download_available",
        "requires_login", "requires_manual_download", "source_page", "http_status", "blocked_reason", "discovered_at",
    ]
    payload = {
        "generated_at": now_iso(), "pages_scanned": pages, "official_documents_found": len(records),
        "downloadable": sum(item["download_available"] for item in records),
        "login_required": sum(item["requires_login"] for item in records),
        "manual_download_required": len(manual), "unsupported_third_party_skipped": third_party_skipped,
        "max_depth": 4, "max_pages": max_pages, "max_documents": max_documents,
        "request_delay_seconds": 1.0, "access_control_bypassed": False,
        "records": records,
    }
    write_json("huawei_discovery.json", payload)
    write_csv("huawei_discovery.csv", fields, records)
    write_json("requires_manual_download.json", {"generated_at": now_iso(), "records": manual})
    print(json.dumps({key: payload[key] for key in ("pages_scanned", "official_documents_found", "downloadable", "login_required", "manual_download_required", "unsupported_third_party_skipped")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
