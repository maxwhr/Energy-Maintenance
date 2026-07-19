from __future__ import annotations

import argparse
import hashlib
import time

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import UploadedMedia
from app.services.multimodal_evidence_service import MultimodalEvidenceService
from app.schemas.multimodal_evidence import MediaProcessingJobCreate
from task25c_common import now_iso, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    allowed = bool(args.allow_real_api and settings.TASK25C_ALLOW_REAL_API)
    payload = {
        "generated_at": now_iso(), "probe": "ocr", "explicit_cli_gate": args.allow_real_api,
        "environment_gate": bool(settings.TASK25C_ALLOW_REAL_API), "external_api_called": False,
        "status": "NOT_EXECUTED_CONFIG_BOUNDARY", "reason": "TASK25C_ALLOW_REAL_API must be true in addition to --allow-real-api",
        "provider": "configured OCR provider (redacted)", "input_hash": None, "output_hash": None, "latency_ms": None,
    }
    if allowed:
        with SessionLocal() as db:
            media = next((item for item in db.query(UploadedMedia).order_by(UploadedMedia.created_at).all()
                          if bool((item.metadata_json or {}).get("engineering_controlled"))), None)
            if media is None:
                payload.update(status="NOT_EXECUTED_NO_AUTHORIZED_MEDIA", reason="no engineering-controlled media")
            else:
                user = media.uploader
                if user is None or user.role not in {"admin", "expert"}:
                    payload.update(status="NOT_EXECUTED_RBAC_BOUNDARY", reason="authorized media uploader is not expert/admin")
                else:
                    started = time.perf_counter()
                    result = MultimodalEvidenceService(db).create_processing_job(media.id, MediaProcessingJobCreate(
                        job_type="ocr", provider_code="custom_ocr_api", capability="ocr", real_run=True,
                        dry_run=False, mock_run=False, input_summary={"task": "task25c_ocr_probe"},
                    ), user)
                    safe = {"status": result.status, "error_code": result.error_code, "provider_code": result.provider_code}
                    payload.update(
                        status="SUCCEEDED" if result.status == "succeeded" else "SAFE_FALLBACK",
                        reason=None if result.status == "succeeded" else "provider unavailable or rejected request",
                        external_api_called=result.status == "succeeded",
                        input_hash=hashlib.sha256(str(media.id).encode()).hexdigest(),
                        output_hash=hashlib.sha256(str(safe).encode()).hexdigest(),
                        latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    )
    write_json("ocr_probe.json", payload)
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
