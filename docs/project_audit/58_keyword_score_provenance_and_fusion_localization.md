# Task 28A-R3H Keyword Score Provenance and Fusion Localization

## Conclusion

The localized root causes are:

- `SCORE_PROVENANCE_LOSS_CONFIRMED`
- `NON_MONOTONIC_RERANK_CONFIRMED`
- `VARIANT_VOTE_MULTIPLICATION_NOT_CONFIRMED`
- `REQUESTED_INFORMATION_OVERMATCH_NOT_CONFIRMED`

The original keyword route calculated lexical relevance while hydrating the
Scope, but `MultiQueryRetrievalService._keyword()` received rank-shaped values
instead of a score-bearing repository contract. Strong and weak candidates at
the same variant rank therefore lost their relevance distance before fusion.

## Code Locations

- Score contract and repository path:
  `backend/app/repositories/retrieval_repository.py`,
  `KeywordCandidateHit` and `list_scored_knowledge_candidates()`.
- Hydrated local scoring:
  `backend/app/services/candidate_hydration_service.py`,
  `rank_keyword_candidate_hits()`.
- Score propagation:
  `backend/app/services/multi_query_retrieval_service.py`, `_keyword()` and
  `_candidate()`.
- Vote selection and fusion:
  `backend/app/services/rrf_fusion_service.py`, `fuse()`.
- Non-monotonic demotion:
  `backend/app/services/deterministic_evidence_rerank_service.py`, `rerank()`.

## Evidence

Before the repair, the normal score fallback ratio was `1.000000`, average raw
variant votes per evidence were `2.305876`, and two direct-evidence cases were
demoted from Fusion Top 3 beyond Top 5. The diagnostic counterfactuals showed
that preserving the real keyword score improved the same-candidate replay,
while query-family vote capping alone did not establish a stable causal gain.

The requested-information overmatch hypothesis had zero confirmed cases.
Accordingly, neither vote multiplication nor requested-information overmatch is
reported as a proven root cause.

## Artifacts

- `.runtime/task28a-r3h/localization/current_pipeline_score_trace.json`
- `.runtime/task28a-r3h/counterfactual/counterfactual_stage_comparison.json`
- `.runtime/task28a-r3h/baseline/pre_change_baseline.json`

No frozen evaluation label, accepted evidence set, reviewer field, database
row, schema, provider, vector index, or QA record was used to alter production
ranking behavior.
