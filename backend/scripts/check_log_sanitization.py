from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.external_api_sanitizer import ExternalApiSanitizer  # noqa: E402


RAW_SECRET = "sk-task24d-secret-should-not-appear-1234567890"
RAW_TOKEN = "Bearer task24d.token.should.not.appear"
RAW_PASSWORD = "password=Task24DPasswordShouldNotAppear"
RAW_WIN_PATH = r"D:\Work Space\Energy-Maintenance\backend\storage\uploads\private.png"
RAW_LINUX_PATH = "/home/user/energy/private.png"
RAW_BASE64 = "data:image/png;base64," + ("A" * 160)


def contains_raw_secret(value: object) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    blocked = [RAW_SECRET, RAW_TOKEN, "Task24DPasswordShouldNotAppear", RAW_WIN_PATH, RAW_LINUX_PATH, "A" * 120]
    return any(item in text for item in blocked)


def main() -> int:
    payload = {
        "Authorization": RAW_TOKEN,
        "api_key": RAW_SECRET,
        "password": "Task24DPasswordShouldNotAppear",
        "safe_business_field": "Huawei SUN2000 insulation alarm inspection",
        "error_message": f"failed with {RAW_SECRET} at {RAW_WIN_PATH}",
        "text": f"{RAW_PASSWORD}; input image {RAW_BASE64}; linux path {RAW_LINUX_PATH}",
        "file_path": RAW_WIN_PATH,
        "image_url": {"url": RAW_BASE64},
        "items": [{"token": RAW_TOKEN}, "normal maintenance text"],
    }
    sanitized = ExternalApiSanitizer.sanitize(payload)
    if contains_raw_secret(sanitized):
        raise AssertionError("sanitized output still contains raw sensitive content")
    if sanitized.get("safe_business_field") != payload["safe_business_field"]:
        raise AssertionError("sanitizer damaged ordinary business text")

    runtime_dir = BACKEND_DIR.parent / ".runtime" / "security"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    output_path = runtime_dir / "log_sanitization_result.json"
    output = {
        "status": "passed",
        "raw_secret_present": False,
        "authorization_present": False,
        "base64_present": False,
        "local_path_present": False,
        "business_text_preserved": True,
        "sample": sanitized,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "sample"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
