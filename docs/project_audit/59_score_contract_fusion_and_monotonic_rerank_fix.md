# Task 28A-R3H Score Contract, Fusion, and Monotonic Rerank Fix

## Implemented Contract

`KeywordCandidateHit` now carries the chunk/document pair plus raw and
normalized relevance scores, repository rank, matched fields/tokens, exact
phrase evidence, score source, fallback flag, and score breakdown. Normal
keyword retrieval propagates `normalized_relevance_score`; `1/rank` is no
longer its sole score.

The normalization is deterministic and Scope-local. It preserves lexical
distance and stable repository order when scores are uniform. The observed
normal-path fallback rate on 514 surfaced Dev candidates is `0.000000`.

## Fusion Contract

Query variants are grouped into ORIGINAL, EXACT_CANONICAL, MODEL, ALARM,
PARAMETER, CAUSE, PROCEDURE, SAFETY, and GENERIC_EXPANSION families. One
evidence identity can contribute at most one primary vote per physical channel;
the best score-aware vote is retained. Independent channels remain eligible.

- Average primary votes per evidence: `2.305876 -> 1.208986`.
- Original primary-vote ratio: `0.658166 -> 0.438890`.
- Selected primary votes after repair: `7642`.
- Original primary votes after repair: `3354`.

The reduced Original ratio is reported rather than hidden. It is one reason the
candidate is not accepted as a complete ranking solution despite passing the
new Dev gate.

## Monotonic Rerank

Direct, conflict-free evidence receives an explicit monotonic anchor strength.
Sorting first respects that protection and then uses deterministic score,
direct-answer, entity, requested-information, original-rank, and identity
tie-breaks. Candidate boundaries and source locators are preserved.

- Confirmed non-monotonic demotions: `2 -> 0` on the independent Dev trace.
- Requested-information overmatch cases: `0 -> 0`.

## Tests and Safety

`backend/tests/unit/test_task28a_r3h_score_contract.py` contains the new score,
normalization, model/alarm, vote-cap, proximity, monotonicity, safety, scope,
and no-hardcoding contracts. The focused plus related suite collected 65 tests
and passed all 65. Backend compileall passed.

The frozen production aggregate SHA-256 remained
`8ba17a3d0ee82e4e57479099146c4460758815ebd58dd30e65182dae22818965`
through final integrity capture. Production-code fixture leakage findings: 0.
