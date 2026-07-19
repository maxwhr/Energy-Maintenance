from __future__ import annotations

import httpx

from task25b_r3_dev_common import DOWNLOADS, MANUAL_SPECS, now_iso, sha256_bytes, write_json


def main() -> None:
    results = []
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://support.huawei.com/enterprise/zh/"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=120) as client:
        for spec in MANUAL_SPECS:
            nid = spec["nid"]
            row = {**spec, "status": "failed"}
            try:
                response = client.get("https://support.huawei.com/supportgateway/view/v1/enterprise/doc/basic", params={"nid": nid})
                response.raise_for_status()
                data = (response.json().get("data") or {})
                main_doc = data.get("mainDoc") or {}
                language = str(data.get("resourceLang") or "").lower()
                if not language.startswith("zh") or not main_doc.get("partNo"):
                    row.update(status="missing_chinese_version", detected_language=language)
                    results.append(row); continue
                url = f"https://download.huawei.com/dl/download.do?actionFlag=download&nid={nid}&partNo={main_doc['partNo']}&mid={data.get('mid') or 'SUPE_DOC'}"
                pdf = client.get(url)
                pdf.raise_for_status()
                if not pdf.content.startswith(b"%PDF"):
                    raise ValueError("official download did not return a PDF")
                path = DOWNLOADS / f"{nid}.pdf"
                path.write_bytes(pdf.content)
                row.update(status="downloaded", title=data.get("name") or data.get("docName") or nid,
                    detected_language="zh-CN", source_url=f"https://support.huawei.com/enterprise/zh/doc/{nid}",
                    download_url=url, file_name=main_doc.get("fileName"), file_size=len(pdf.content),
                    sha256=sha256_bytes(pdf.content), local_path=str(path), official_domain="support.huawei.com")
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
            results.append(row)
    payload = {"generated_at": now_iso(), "official_only": True, "machine_translation_used": False,
               "downloaded": sum(item["status"] == "downloaded" for item in results), "documents": results}
    write_json("chinese_manual_discovery.json", payload)
    print({"status": "passed" if payload["downloaded"] else "failed", "downloaded": payload["downloaded"]})


if __name__ == "__main__": main()
