from __future__ import annotations

import argparse
import math
import time

from task25b_common import real_gate, write_result
from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService


def cosine(left, right):
    dot = sum(a * b for a, b in zip(left, right))
    return dot / ((sum(a * a for a in left) ** .5 or 1) * (sum(b * b for b in right) ** .5 or 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    allowed, reasons = real_gate(settings, args.allow_real_api)
    if not allowed:
        write_result("embedding_real.json", {"status": "BLOCKED_CONFIG", "reasons": reasons, "external_api_called": False})
        return 2
    service = EmbeddingService(allow_real_api=True)
    started = time.perf_counter()
    single = service.embed_text("华为 SUN2000-100KTL 告警 2064 绝缘阻抗排查", provider="dashscope_openai_compatible")
    batch_texts = [f"光伏逆变器检修语义顺序探针 {index}" for index in range(10)]
    batch = service.embed_texts(batch_texts, provider="dashscope_openai_compatible")
    related = service.embed_texts(["逆变器绝缘阻抗低排查", "光伏设备绝缘电阻异常检查", "食堂午餐菜单"], provider="dashscope_openai_compatible")
    finite = all(math.isfinite(value) for vector in [*single.vectors, *batch.vectors] for value in vector)
    semantic = cosine(related.vectors[0], related.vectors[1]) > cosine(related.vectors[0], related.vectors[2])
    passed = single.dimension == 1024 and len(batch.vectors) == 10 and finite and semantic
    write_result("embedding_real.json", {
        "status": "PASSED" if passed else "FAILED", "external_api_called": True,
        "provider": single.provider, "model": single.model, "dimension": single.dimension,
        "single_call": True, "batch_call_count": len(batch.vectors), "order_count_preserved": len(batch.vectors) == len(batch_texts),
        "finite_values": finite, "semantic_probe": semantic, "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "single_metadata": single.metadata, "batch_metadata": batch.metadata,
        "key_output": False, "full_vectors_output": False,
    })
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
