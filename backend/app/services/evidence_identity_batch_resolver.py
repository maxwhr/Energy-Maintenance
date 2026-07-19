from __future__ import annotations

from app.services.evidence_identity_service import EvidenceIdentityService


class EvidenceIdentityBatchResolver:
    def resolve(self, rankings: dict[str, list]) -> dict:
        service = EvidenceIdentityService()
        resolved: dict[str, dict] = {}
        candidates = 0
        reused = 0
        failures: list[dict] = []
        for values in rankings.values():
            for candidate in values:
                candidates += 1
                cache_key = candidate.candidate_id
                cached = resolved.get(cache_key)
                if cached is not None:
                    candidate.evidence_identity = cached["identity"]
                    candidate.evidence_equivalence_key = cached["equivalence_key"]
                    candidate.evidence_level = cached["level"]
                    candidate.evidence_aliases.update(cached["aliases"])
                    reused += 1
                    continue
                try:
                    identity = service.apply(candidate)
                    resolved[cache_key] = {
                        "identity": identity.primary_id,
                        "equivalence_key": identity.equivalence_key,
                        "level": identity.level,
                        "aliases": set(identity.aliases),
                    }
                except Exception as exc:  # noqa: BLE001 - candidate is retained and failure is explicit.
                    failures.append({"candidate_id": cache_key, "reason": type(exc).__name__})
        return {
            "candidate_rows": candidates,
            "unique_candidates": len(resolved),
            "identity_reuse_count": reused,
            "failure_count": len(failures),
            "failures": failures,
            "candidates_dropped": 0,
        }
