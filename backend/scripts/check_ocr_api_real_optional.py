from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.services.external_api_provider_registry import ExternalApiProviderRegistry  # noqa: E402
from scripts.task24c_real_api_common import (  # noqa: E402
    MARKER,
    SAMPLE_PNG,
    api_data,
    contains_sensitive_value,
    login,
    missing_config,
    print_result,
    provider_config_summary,
    query_string,
    request_json,
    upload_test_media,
    write_result,
)


def _seed_providers() -> None:
    with SessionLocal() as db:
        ExternalApiProviderRegistry(db).seed_defaults()
        db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional real OCR API acceptance check.")
    parser.add_argument("--allow-real-api", action="store_true", help="Actually call the configured OCR API provider.")
    parser.add_argument("--base-url", default=None, help="API base URL, defaults to TASK24C_API_BASE_URL or 127.0.0.1:8010/api.")
    args = parser.parse_args()

    if not args.allow_real_api:
        result = {
            "provider": "ocr_api",
            "status": "skipped",
            "reason": "real OCR API check requires --allow-real-api",
            "real_external_api_used": False,
            "config": provider_config_summary()["ocr_api"],
        }
        write_result("ocr_api_real_result.json", result)
        print_result(result)
        return 0

    missing = missing_config("ocr_api")
    if missing:
        result = {
            "provider": "ocr_api",
            "status": "blocked",
            "missing_or_invalid": missing,
            "real_external_api_used": False,
            "config": provider_config_summary()["ocr_api"],
        }
        write_result("ocr_api_real_result.json", result)
        print_result(result)
        return 0

    _seed_providers()
    token, user = login(args.base_url)
    media_id = upload_test_media(token, base_url=args.base_url, marker=MARKER)
    image_base64 = base64.b64encode(SAMPLE_PNG).decode("ascii")
    status, response = request_json(
        "POST",
        f"/multimodal/media/{media_id}/jobs",
        base_url=args.base_url,
        token=token,
        payload={
            "job_type": "ocr",
            "provider_code": "custom_ocr_api",
            "capability": "ocr",
            "dry_run": False,
            "mock_run": False,
            "real_run": True,
            "input_summary": {
                "acceptance_marker": MARKER,
                "prompt": "Extract visible text from this PV inverter acceptance fixture. Return JSON.",
                "image_base64": image_base64,
                "mime_type": "image/png",
                "image_count": 1,
                "language": "chi_sim+eng",
            },
        },
        timeout=120,
    )
    job = api_data("ocr real job", status, response)
    job_status = job.get("status") if isinstance(job, dict) else None
    job_id = job.get("id") if isinstance(job, dict) else None
    trace_id = job.get("external_trace_id") if isinstance(job, dict) else None

    query = query_string({"page": 1, "page_size": 20})
    status, response = request_json("GET", f"/multimodal/media/{media_id}/ocr-results?{query}", base_url=args.base_url, token=token)
    ocr_page = api_data("ocr results list", status, response)
    results = ocr_page.get("items") if isinstance(ocr_page, dict) else []
    ocr = next((item for item in results if str(item.get("job_id")) == str(job_id)), None)
    raw_result = (ocr or {}).get("raw_result_json") if isinstance(ocr, dict) else {}
    persisted = bool(
        job_status == "succeeded"
        and ocr
        and isinstance(raw_result, dict)
        and raw_result.get("real_external_api_used") is True
        and raw_result.get("mocked") is False
    )

    status, response = request_json("GET", f"/external-apis/logs/{trace_id}", base_url=args.base_url, token=token) if trace_id else (404, {})
    log_detail = api_data("ocr external log detail", status, response) if status < 400 else {}

    sensitive = contains_sensitive_value(job) or contains_sensitive_value(ocr or {}) or contains_sensitive_value(log_detail)
    status_value = "passed" if persisted and not sensitive else "failed"
    result = {
        "provider": "custom_ocr_api",
        "status": status_value,
        "real_external_api_used": bool(persisted),
        "media_id": media_id,
        "job_id": job_id,
        "job_status": job_status,
        "trace_id": trace_id,
        "ocr_result_id": ocr.get("id") if isinstance(ocr, dict) else None,
        "ocr_result_persisted": persisted,
        "text_length": len(str(ocr.get("text") or "")) if isinstance(ocr, dict) else 0,
        "mocked": raw_result.get("mocked") if isinstance(raw_result, dict) else None,
        "logs_sanitized": not sensitive,
        "human_review_boundary": "OCR result is auxiliary evidence and requires human review before maintenance decisions.",
        "config": provider_config_summary()["ocr_api"],
        "current_user": {"username": user.get("username"), "role": user.get("role")},
    }
    write_result("ocr_api_real_result.json", result)
    print_result(result)
    return 0 if status_value == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
