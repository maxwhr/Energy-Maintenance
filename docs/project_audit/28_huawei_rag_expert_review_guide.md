# Huawei SUN2000 RAG Expert Review Guide

## Review Status

- Dataset: `task27a_huawei_sun2000_engineering_candidate_v1`
- Version: `1.0.0`
- Frozen SHA-256: `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`
- Cases: 30
- Current status: `ENGINEERING_CANDIDATE`
- Expert review: `PENDING`

The engineering evaluation has passed its strict automated gates. This does not make the dataset expert-reviewed and does not authorize a `READY` claim.

## Review Material

Use `28_huawei_rag_expert_review_sheet.csv`. The frozen JSON fixture must not be edited during review. The sheet contains the frozen expectations together with the current Top 5 evidence, generated answer, and source references from the final read-only R3 evaluation.

## Review Procedure

For every row:

1. Confirm that the manufacturer, model, alarm code, expected documents, and expected chunks are technically appropriate for the query.
2. Confirm that every required answer point is necessary and supported by the cited source.
3. Confirm that no prohibited claim appears and that the answer does not overstate a diagnosis.
4. Check each reference against the source chunk, including model applicability and the surrounding section context.
5. For electrical work, confirm that the safety guidance is sufficient and does not authorize unsafe field action.
6. For out-of-scope or no-data cases, confirm that abstention is the correct behavior.
7. Fill all expert fields, add specific comments where a correction is required, then provide reviewer name and review date.

## Allowed Review Values

- `expert_conclusion`: `accept`, `accept_with_changes`, or `reject`
- `labels_accurate`: `true` or `false`
- `answer_acceptable`: `true` or `false`
- `citation_supports`: `true` or `false`
- `safety_sufficient`: `true`, `false`, or `not_applicable`
- `expert_reviewed`: set to `true` only after the row is actually reviewed
- `review_status`: `approved`, `changes_required`, or `rejected`

Do not pre-fill approval values. A human Huawei inverter-maintenance expert must make and sign each decision.

## Decision Boundary

Automated metrics may support engineering acceptance only. Final dataset acceptance requires all 30 rows to be reviewed, reviewer identity and date to be recorded, disagreements to be resolved, and any label changes to go through a separately versioned review process rather than silently modifying the frozen fixture.
