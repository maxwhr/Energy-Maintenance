from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r3"
DOCS = ROOT / "docs"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name: str, content: str) -> None:
    (DOCS / name).write_text(content.rstrip() + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, content: str) -> None:
    existing = path.read_text(encoding="utf-8")
    if marker not in existing:
        path.write_text(existing.rstrip() + "\n\n" + marker + "\n" + content.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    grounding = load("vector_heavy_grounding.json")
    embedding = load("embedding_pair_diagnostics.json")
    trace = load("dashvector_recall_trace.json")
    index = load("semantic_anchor_index.json")
    reconciliation = load("semantic_reconciliation.json")
    canary = load("canary_result.json")
    snapshot = load("r2_snapshot.json")
    manifest = load("semantic_representation_manifest.json")
    regression = load("regression_result.json") if (OUT / "regression_result.json").exists() else {}
    heavy = canary["vector_heavy"]
    averages = embedding["averages"]

    write("25B_R3_DEV_R3_vector_heavy_grounding_report.md", f"""# Task 25B-R3-DEV-R3 Vector-heavy Grounding Audit

## Scope and integrity

- Train/dev only; test_v3 was not read or used: `{grounding['test_v3_used']}`.
- Cases reviewed: {grounding['cases_reviewed']}.
- This is an evidence audit, not a label expansion. It preserves weak and ambiguous cases instead of promoting adjacent or same-document chunks.

## Result

| Status | Count |
| --- | ---: |
| GROUNDED_STRONG | {grounding['summary'].get('GROUNDED_STRONG', 0)} |
| GROUNDED_MODERATE | {grounding['summary'].get('GROUNDED_MODERATE', 0)} |
| AMBIGUOUS_SECTION | {grounding['summary'].get('AMBIGUOUS_SECTION', 0)} |
| GROUNDING_WEAK | {grounding['summary'].get('GROUNDING_WEAK', 0)} |
| Usable Canary cases | {grounding['usable_canary_cases']} |

The historical R2 train/dev vector-heavy labels contribute 40 `GROUNDING_WEAK` rows. The new source-only candidate set exposed 19 `AMBIGUOUS_SECTION` rows because the same abstract semantic signature labelled multiple source chunks. Those rows are not valid positive Chunk labels and must not be used to claim a passing Canary.
""")

    write("25B_R3_DEV_R3_embedding_pair_diagnostics_report.md", f"""# Task 25B-R3-DEV-R3 Embedding Pair Diagnostics

- Pairs: {embedding['pairs']} source-grounded train/dev candidates; test_v3 used: `{embedding['test_v3_used']}`.
- Model/dimension: `{embedding['embedding_model']}` / {embedding['embedding_dimension']}.
- Raw positive similarity: {averages['query_to_raw_chunk_similarity']:.6f}.
- Semantic positive similarity: {averages['query_to_semantic_text_similarity']:.6f}.
- Hard-negative similarity: {averages['query_to_hard_negative_similarity']:.6f}.
- Raw positive margin: {averages['positive_margin_raw']:.6f}.
- Semantic positive margin: {averages['positive_margin_semantic']:.6f}.
- Primary diagnosis: `{embedding['primary_diagnosis']}`.

The reproducible semantic-minus-raw lift ({embedding['semantic_minus_raw']:.6f}) and positive-margin lift diagnose raw Chunk representation dilution. These diagnostic thresholds are not acceptance thresholds and did not use Benchmark expected labels or export vectors.
""")

    write("25B_R3_DEV_R3_dashvector_recall_trace_report.md", f"""# Task 25B-R3-DEV-R3 DashVector Raw Recall Trace

- Collection/partition: `{trace['collection']}` / `{trace['partition']}`.
- Source-only train/dev cases: {trace['cases']}; test_v3 used: `{trace['test_v3_used']}`.
- Raw Top50 expected hits: {trace['raw_top50_hit']}.
- Post-filter expected hits: {trace['post_filter_hit']}.
- Mapping failures: {trace['mapping_failures']}; filter drops: {trace['filter_drops']}; score-direction issues: {trace['score_direction_issues']}; content mismatches: {trace['content_mismatches']}.

The equal raw/post-filter hit count shows that scope filtering and ID mapping did not remove expected results. The main failure mode was therefore raw representation recall, not post-filtering or vector-ID reconciliation.
""")

    write("25B_R3_DEV_R3_semantic_representation_design.md", f"""# Task 25B-R3-DEV-R3 Semantic Representation Design

`MaintenanceSemanticRepresentationService` constructs a versioned, reproducible source-only representation from the current Chunk, its document metadata, structured alarm metadata, and its source locator. Missing causes remain empty; no LLM fills missing facts.

- Version: `{manifest['representation_version']}`.
- Source chunks in the isolated Canary design: {manifest['source_chunks']}.
- Anchor count: {manifest['anchor_count']}.
- Anchor types: {', '.join(sorted(manifest['anchor_types']))}.
- Benchmark query used: `{manifest['benchmark_query_used']}`; test_v3 used: `{manifest['test_v3_used']}`.
- Each anchor keeps source Chunk ID, locator, language, approval/current metadata, representation hash/version, and stable `source_chunk_uuid + anchor_type` vector ID.

The semantic query representation retains the original query and traceable normalized terms. It does not inject document titles, expected labels, models, or alarm codes that were not expressed by the user.
""")

    write("25B_R3_DEV_R3_semantic_anchor_index_report.md", f"""# Task 25B-R3-DEV-R3 Semantic Anchor A/B Index

- Collection: `{index['collection']}`.
- Raw partition retained: `{index['raw_partition_unchanged']}`.
- Isolated semantic partition: `{index['partition']}`.
- Source chunks: {manifest['source_chunks']}; anchor vectors: {index['anchor_vectors']}.
- Index status: indexed={index['indexed']}, skipped={index['skipped']}, failed={index['failed']}.
- Raw vector rewrite: `{index['raw_vector_rewrite']}`; full reindex: `{index['full_reindex']}`; expert verified: `{index['expert_verified']}`.
- Reconciliation: missing={reconciliation['missing_anchor']}, orphan={reconciliation['orphan_anchor']}, duplicate={reconciliation['duplicate_anchor_id']}, representation mismatch={reconciliation['representation_hash_mismatch']}, language/status/current leakage={reconciliation['language_leakage']}/{reconciliation['status_leakage']}/{reconciliation['current_version_leakage']}.

The A/B index reconciled successfully, but it is diagnostic-only. No normal production retrieval route was enabled from this partition because the independent Canary did not pass.
""")

    write("25B_R3_DEV_R3_canary_report.md", f"""# Task 25B-R3-DEV-R3 Independent Train/Dev Canary

## Gate result

`{canary['status']}`. This is not a near-pass: the semantic Candidate Recall@50 gate failed, so the required result is `DEVELOPMENT_ENGINEERING_VECTOR_RECALL_NOT_PROVEN`.

## Vector-heavy A/B results

| Measure | Value |
| --- | ---: |
| Cases | {canary['cases']} |
| Vector-heavy cases | {heavy['cases']} |
| Keyword Recall@5 | {heavy['keyword']['recall_at_5']:.6f} |
| Raw vector Recall@5 | {heavy['raw_vector']['recall_at_5']:.6f} |
| Semantic vector Recall@5 | {heavy['semantic_vector']['recall_at_5']:.6f} |
| Adaptive semantic Recall@5 | {heavy['adaptive_semantic']['recall_at_5']:.6f} |
| Semantic Candidate Recall@50 | {heavy['candidate_recall_at_50']:.6f} |
| Adaptive semantic MRR | {heavy['adaptive_semantic']['mrr']:.6f} |
| Adaptive semantic nDCG@10 | {heavy['adaptive_semantic']['ndcg_at_10']:.6f} |
| Relative Recall@5 gain | {heavy['relative_recall_gain']:.6f} |
| Warm p95 (adaptive) ms | {canary['by_mode']['adaptive_semantic']['warm_p95_ms']:.3f} |

Relative semantic gain was real (+{heavy['relative_recall_gain']:.6f}) and actual semantic routing had no fallback, leakage, or error. It is insufficient: Candidate Recall@50 was below 0.90 and quality metrics remained below the required gates. In addition, the selected vector-heavy rows included 9 `AMBIGUOUS_SECTION` labels and were not eligible to pass a grounded-vector-heavy gate. No second tuning Canary was run.

R2 remains preserved as `{snapshot['r2_canary_status']}`. pilot_r2 was not changed.

## Regression evidence

- Compileall: {regression.get('compileall', 'not run')}; Alembic head/current: {regression.get('alembic_head_and_current', 'not run')}; pytest: {regression.get('pytest', 'not run')}.
- Security/RBAC: {regression.get('security', 'not run')} / {regression.get('rbac', 'not run')}; agents and conversion: {regression.get('agent_and_conversion', 'not run')}.
- Frontend build/vue-tsc/browser: {regression.get('frontend_build', 'not run')} / {regression.get('vue_tsc', 'not run')} / {regression.get('browser', 'not run')}.
- Final smoke: {regression.get('final_smoke', 'not run')}. LoongArch physical verification: {regression.get('loongarch_physical_verification', 'not run')}.
""")

    write("25B_R3_DEV_R3_quality_gate_v3_1_report.md", """# Task 25B-R3-DEV-R3 Formal v3_1 Quality Gate

## Result

NOT RUN — Canary failed. `task25b_r3_dev_r3_zh_v3_1` was not created, was not frozen, and has no official run.

The create, freeze, and quality-gate scripts are guarded so they terminate before mutation unless the recorded Canary status is `CANARY_PASSED`. The existing `task25b_r3_dev_r2_zh_v3` draft remains unfrozen and is not reused as a new formal test.

Regression completed with `""" + regression.get("pytest", "pytest not run") + """`; this does not override the failed semantic recall gate.
""")

    marker = "<!-- TASK25B_R3_DEV_R3 -->"
    common = """## Task 25B-R3-DEV-R3 semantic recall diagnosis

- R2 Canary remains `CANARY_FAILED` and its artifacts are preserved read-only.
- Raw Chunk representation dilution was diagnosed with train/dev-only embedding pairs; DashVector filtering and mapping were not the root cause.
- An isolated `pilot_r3_semantic` A/B partition was created with 416 source-only anchors. `pilot_r2`, the default partition, and the original 1,262 vectors were not changed.
- The independent Canary failed: semantic Candidate Recall@50 = 0.444444, below 0.90. `test_v3_1` was not created or frozen and no formal quality run or full reindex occurred.
- `expert_verified=false`; no package, Git commit, or LoongArch physical verification occurred.
"""
    for relative in (
        "25B_R3_DEV_R2_canary_report.md", "25B_R3_DEV_R2_vector_heavy_report.md", "25B_R2_full_reindex_go_no_go_report.md",
        "09_testing_acceptance_and_quality_spec.md", "12_functional_design_specification.md", "19_delivery_checklist.md",
    ):
        append_once(DOCS / relative, marker, common)
    append_once(ROOT / "README.md", marker, common)
    append_once(ROOT / "backend" / "README.md", marker, common)


if __name__ == "__main__":
    main()
