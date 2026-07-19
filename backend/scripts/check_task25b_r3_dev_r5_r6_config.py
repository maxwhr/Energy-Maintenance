from __future__ import annotations

import json

from app.core.config import get_settings
from task25b_r3_dev_r5_r6_common import write_json


def main() -> None:
    settings = get_settings()
    checks = {
        "dashscope_api_key_present": bool(settings.DASHSCOPE_API_KEY.strip()),
        "workspace_base_url_present": bool(settings.DASHSCOPE_RERANK_BASE_URL.strip()),
        "endpoint_present": bool(settings.DASHSCOPE_RERANK_ENDPOINT.strip()),
        "model_present": bool(settings.DASHSCOPE_RERANK_MODEL.strip()),
        "provider_is_dashscope": settings.RAG_DEDICATED_RERANK_PROVIDER.lower() == "dashscope",
        "model_alignment": settings.RAG_DEDICATED_RERANK_MODEL == settings.DASHSCOPE_RERANK_MODEL,
        "max_documents_bounded_20_50": 20 <= settings.DASHSCOPE_RERANK_MAX_DOCUMENTS <= 50,
        "top_n_bounded": 1 <= settings.DASHSCOPE_RERANK_TOP_N <= settings.DASHSCOPE_RERANK_MAX_DOCUMENTS,
        "provider_enabled": settings.DASHSCOPE_RERANK_ENABLED and settings.RAG_DEDICATED_RERANK_ENABLED,
        "full_reindex_disabled": not settings.TASK25B_ALLOW_FULL_REINDEX,
    }
    required = (
        checks["dashscope_api_key_present"]
        and checks["workspace_base_url_present"]
        and checks["endpoint_present"]
        and checks["model_present"]
        and checks["provider_is_dashscope"]
        and checks["model_alignment"]
        and checks["provider_enabled"]
    )
    status = "QWEN3_RERANK_CONFIG_READY" if required else "QWEN3_RERANK_CONFIG_MISSING"
    payload = {
        "status": status,
        "checks": checks,
        "enabled": settings.DASHSCOPE_RERANK_ENABLED and settings.RAG_DEDICATED_RERANK_ENABLED,
        "provider": settings.RAG_DEDICATED_RERANK_PROVIDER,
        "model": settings.DASHSCOPE_RERANK_MODEL,
        "endpoint_path": settings.DASHSCOPE_RERANK_ENDPOINT,
        "timeout_seconds": settings.DASHSCOPE_RERANK_TIMEOUT_SECONDS,
        "max_documents": settings.DASHSCOPE_RERANK_MAX_DOCUMENTS,
        "top_n": settings.DASHSCOPE_RERANK_TOP_N,
        "cache_enabled": settings.DASHSCOPE_RERANK_CACHE_ENABLED,
        "base_url_value_exposed": False,
        "api_key_value_exposed": False,
        "workspace_url_inferred": False,
    }
    write_json("config_check.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    if not required:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
