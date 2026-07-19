from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.schemas.retrieval_plan import RetrievalPlan, RetrievalQueryVariant


@dataclass(slots=True)
class QueryVariantDeduplicationResult:
    plan: RetrievalPlan
    diagnostics: dict


class QueryVariantDeduplicationService:
    @staticmethod
    def normalize(value: str) -> str:
        return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()

    def deduplicate(self, plan: RetrievalPlan) -> QueryVariantDeduplicationResult:
        seen: dict[str, RetrievalQueryVariant] = {}
        kept: list[RetrievalQueryVariant] = []
        removed: list[dict] = []
        for variant in plan.query_variants:
            normalized = self.normalize(variant.query)
            key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            existing = seen.get(key)
            if existing is not None:
                removed.append({
                    "variant_type": variant.variant_type,
                    "normalized_hash": key,
                    "reason": "NORMALIZED_DUPLICATE",
                    "duplicate_of": existing.variant_type,
                })
                continue
            seen[key] = variant
            kept.append(variant)
        kept_queries = {item.query for item in kept}
        channel_queries = {
            channel: list(dict.fromkeys(
                query for query in queries
                if query in kept_queries or channel == "EXACT_KEYWORD"
            ))
            for channel, queries in plan.channel_queries.items()
        }
        updated = plan.model_copy(update={"query_variants": kept, "channel_queries": channel_queries})
        generated = len(plan.query_variants)
        unique = len(kept)
        return QueryVariantDeduplicationResult(updated, {
            "variants_generated": generated,
            "variants_unique": unique,
            "variants_removed": generated - unique,
            "duplicate_ratio": round((generated - unique) / generated, 6) if generated else 0.0,
            "embedding_calls_saved": generated - unique,
            "provider_calls_saved": generated - unique,
            "removed": removed,
            "case_id_used": False,
            "benchmark_labels_used": False,
        })
