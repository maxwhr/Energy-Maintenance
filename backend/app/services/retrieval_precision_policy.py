from __future__ import annotations

from collections import Counter

from app.services.hybrid_retrieval_service import HybridScoredCandidate


class RetrievalPrecisionPolicy:
    """Conservative display cutoff; it never reads benchmark labels or expected IDs."""

    @staticmethod
    def apply(
        candidates: list[HybridScoredCandidate],
        *,
        requested_top_k: int,
        minimum_score: float,
    ) -> tuple[list[HybridScoredCandidate], dict]:
        if not candidates:
            return [], {"input": 0, "output": 0, "collapsed": 0, "policy": "precision_v1"}
        limit = min(5, max(1, requested_top_k))
        top_score = max(0.0, float(candidates[0].score))
        display_floor = max(float(minimum_score), top_score * 0.55)
        output: list[HybridScoredCandidate] = []
        per_document: Counter = Counter()
        for rank, candidate in enumerate(candidates, 1):
            exact = bool(candidate.exact_model_boost or candidate.exact_fault_code_boost)
            if rank > 3 and not exact and float(candidate.score) < display_floor:
                continue
            if per_document[candidate.document.id] >= 2 and not exact:
                continue
            output.append(candidate)
            per_document[candidate.document.id] += 1
            if len(output) >= limit:
                break
        return output, {
            "input": len(candidates), "output": len(output), "collapsed": len(candidates) - len(output),
            "display_floor": round(display_floor, 6), "top3_priority": True,
            "maximum_displayed": limit, "same_document_soft_limit": 2, "policy": "precision_v1",
        }
