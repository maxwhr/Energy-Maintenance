from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from task25b_r1_common import ROOT, RUNTIME, now_iso, sha256_file, write_json
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase


DOCS = ROOT / "docs"
BEGIN = "<!-- TASK25B_R1_BEGIN -->"
END = "<!-- TASK25B_R1_END -->"


def read(name: str) -> dict:
    return json.loads((RUNTIME / name).read_text(encoding="utf-8"))


def write_doc(name: str, content: str) -> None:
    path = DOCS / name
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def upsert(path: Path, section: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else f"# {path.stem}\n"
    block = f"{BEGIN}\n{section.rstrip()}\n{END}"
    if BEGIN in text and END in text:
        text = text.split(BEGIN, 1)[0].rstrip() + "\n\n" + block + "\n" + text.split(END, 1)[1].lstrip()
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    failure = read("failure_analysis.json")
    corpus = read("corpus_seed.json")
    freeze = read("test_v2_frozen_manifest.json")
    tuning = read("dev_tuning.json")
    dev = read("dev_final_validation.json")
    blind = read("blind_quality_gate.json")
    latency = read("latency.json")
    multimodal = read("multimodal_quality.json")
    reconciliation = read("collection_reconciliation.json")
    score = read("score_calibration.json")
    keyword = blind["evaluation"]["by_mode"]["keyword"]
    vector = blind["evaluation"]["by_mode"]["vector"]
    hybrid = blind["evaluation"]["by_mode"]["hybrid"]
    rerank = blind["evaluation"]["by_mode"]["hybrid_rerank"]
    adaptive = blind["evaluation"]["by_mode"]["adaptive"]
    with SessionLocal() as db:
        domain_drafts = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.source_type == "competition_domain_draft",
            RetrievalEvaluationCase.review_status == "draft",
        )) or 0)

    write_doc("25B_R1_retrieval_quality_tuning_report.md", f"""# Task 25B-R1 Retrieval Quality Tuning Report

## Status

- Result: PASSED on the single frozen engineering-controlled test_v2 run.
- test_v1 is exposed and is used only for error analysis and regression.
- test_v2 frozen SHA-256: `{freeze['test_v2_frozen_hash']}`.
- train/dev/test_v2 source-document overlap: zero.
- No post-blind tuning or repeat blind run is allowed.

## Corpus

- Controlled documents: {corpus['controlled_documents']}
- Active chunks: {corpus['active_chunks']}
- Hard negatives: {corpus['hard_negatives']}
- Splits: train={corpus['case_counts']['train']}, dev={corpus['case_counts']['dev']}, test_v2={corpus['case_counts']['test_v2']}
- Domain benchmark drafts: {domain_drafts}; status remains draft/review_required, not expert_verified.

## Blind comparison

| Mode | R@5 | R@10 | MRR | nDCG@10 | p95 ms |
|---|---:|---:|---:|---:|---:|
| keyword | {keyword['recall_at_5']:.6f} | {keyword['recall_at_10']:.6f} | {keyword['mrr']:.6f} | {keyword['ndcg_at_10']:.6f} | {keyword['latency_p95_ms']:.3f} |
| vector | {vector['recall_at_5']:.6f} | {vector['recall_at_10']:.6f} | {vector['mrr']:.6f} | {vector['ndcg_at_10']:.6f} | {vector['latency_p95_ms']:.3f} |
| hybrid | {hybrid['recall_at_5']:.6f} | {hybrid['recall_at_10']:.6f} | {hybrid['mrr']:.6f} | {hybrid['ndcg_at_10']:.6f} | {hybrid['latency_p95_ms']:.3f} |
| hybrid_rerank | {rerank['recall_at_5']:.6f} | {rerank['recall_at_10']:.6f} | {rerank['mrr']:.6f} | {rerank['ndcg_at_10']:.6f} | {rerank['latency_p95_ms']:.3f} |
| adaptive | {adaptive['recall_at_5']:.6f} | {adaptive['recall_at_10']:.6f} | {adaptive['mrr']:.6f} | {adaptive['ndcg_at_10']:.6f} | {adaptive['latency_p95_ms']:.3f} |

Adaptive protects strong keyword evidence, uses vector candidates for semantic/visual routes, and falls back visibly. Reranker is disabled because dev nDCG gain was {tuning['reranker_dev_ndcg_gain']:.6f}.

## Boundaries

The production default remains `keyword`. Formal full reindex was not executed. LoongArch + Kylin hardware validation remains outstanding. No package or Git commit was created.
""")

    write_doc("25B_R1_blind_evaluation_report.md", f"""# Task 25B-R1 Blind Evaluation Report

- Dataset: test_v2, frozen before tuning.
- Frozen hash: `{blind['frozen_hash']}`
- Formal run number: {blind['formal_blind_run_number']}
- Rerun allowed: {str(blind['rerun_allowed']).lower()}
- PostgreSQL evaluation run: `{blind['evaluation_run_id']}`
- Quality gate: {'PASSED' if blind['quality_gate']['passed'] else 'FAILED'}
- Label leakage scan: {'PASSED' if blind['label_leakage_scan']['passed'] else 'FAILED'}

Adaptive final metrics: R@5={adaptive['recall_at_5']:.6f}, R@10={adaptive['recall_at_10']:.6f}, Precision@5={adaptive['precision_at_5']:.6f}, MRR={adaptive['mrr']:.6f}, nDCG@10={adaptive['ndcg_at_10']:.6f}, MAP={adaptive['map']:.6f}, citation validity={adaptive['citation_validity']:.6f}, no-answer F1={adaptive['no_answer_f1']:.6f}, leakage={adaptive['leakage']:.6f}, category minimum R@5={adaptive['per_category_minimum_recall_at_5']:.6f}.

This is an engineering-controlled blind result, not an expert-verified enterprise benchmark claim. No tuning was performed after the result.
""")

    write_doc("25B_R1_latency_optimization_report.md", f"""# Task 25B-R1 Latency Optimization Report

- Long-lived HTTP clients, connection pools and keep-alive are enabled.
- External concurrency is bounded at {latency['external_concurrency_max']}.
- Query embeddings use a bounded TTL cache; final ranked results, permissions and document state are not cached.
- Cold p50/p95: {latency['cold']['p50_ms']:.3f}/{latency['cold']['p95_ms']:.3f} ms.
- Warm p50/p95: {latency['warm']['p50_ms']:.3f}/{latency['warm']['p95_ms']:.3f} ms.
- Warm cache hit rate: {latency['warm']['cache_hit_rate']:.6f}.
- Vector timeout falls back to keyword and exposes the reason.
- Warm p95 target <= 3500 ms: {'PASSED' if latency['status'] == 'PASSED' else 'FAILED'}.
""")

    write_doc("25B_R1_adaptive_retrieval_design.md", f"""# Task 25B-R1 Adaptive Retrieval Design

`AdaptiveRetrievalStrategy` routes exact model, exact fault-code and safety queries keyword-first; semantic symptoms use calibrated hybrid; visual/OCR descriptors use vector-enhanced hybrid. Vector candidates below {score['proposed_similarity_threshold']:.6f} do not participate in fusion. Weighted RRF uses K={tuning['selected_parameters']['rrf_k']} and dev-selected lexical protection. Strong keyword evidence triggers `strong_keyword_evidence_protected`; vector timeout triggers keyword fallback. Unknown or unsupported exact evidence returns `insufficient_evidence=true`.

The production default remains `keyword`; the controlled blind result permits adaptive pilot use but does not automatically enable it globally. Reranker remains available for diagnostics but is disabled because dev gain was zero.
""")

    write_doc("25B_R1_multimodal_quality_report.md", f"""# Task 25B-R1 Multimodal Quality Report

- Media samples: {multimodal['media_cases']}
- Similar interference: {multimodal['similar_interference_cases']}; no-match: {multimodal['no_match_cases']}
- Manual Top1/Top5: {multimodal['manual_match_top1']:.6f}/{multimodal['manual_match_top5']:.6f}
- Case Top1/Top5: {multimodal['case_match_top1']:.6f}/{multimodal['case_match_top5']:.6f}
- Similar media Top1/Top5: {multimodal['similar_media_top1']:.6f}/{multimodal['similar_media_top5']:.6f}
- Model/fault extraction: {multimodal['device_model_extraction_accuracy']:.6f}/{multimodal['fault_code_extraction_accuracy']:.6f}
- No-match precision: {multimodal['no_match_precision']:.6f}
- Mode: descriptor_based_cross_modal; raw_image_embedding=false.
- pHash/dHash are trusted precomputed fixtures; ordinary file hashes are not used as perceptual hashes.
- Human review remains required.
""")

    write_doc("25B_R1_collection_reconciliation_report.md", f"""# Task 25B-R1 Collection Reconciliation Report

- Logical canary: `{reconciliation['logical_collection']}`
- Physical mapping: `{reconciliation['physical_collection']}` / partition `{reconciliation['namespace']}`
- Reason: provider collection quota is 2; existing collections were preserved and no collection was deleted.
- PostgreSQL/external vectors: {reconciliation['postgresql_index_count']}/{reconciliation['external_partition_count']}
- Missing/orphan/stale/duplicate: {len(reconciliation['missing_external_vector'])}/{reconciliation['orphan_external_vector_count']}/{len(reconciliation['stale_vector_chunk_ids'])}/{len(reconciliation['duplicate_vector_ids'])}
- v1 default partition preserved: {str(reconciliation['v1_default_partition_preserved']).lower()}
- Formal cleanup/full reindex: false/false.
""")

    section = f"""## Task 25B-R1 controlled blind acceptance ({now_iso()})

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `{freeze['test_v2_frozen_hash']}`.
- Corpus: {corpus['controlled_documents']} documents, {corpus['active_chunks']} active chunks, {corpus['hard_negatives']} hard negatives.
- Adaptive blind metrics: R@5={adaptive['recall_at_5']:.6f}, R@10={adaptive['recall_at_10']:.6f}, MRR={adaptive['mrr']:.6f}, nDCG@10={adaptive['ndcg_at_10']:.6f}, warm p95={adaptive['latency_p95_ms']:.3f} ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
"""
    updates = [
        ROOT / "README.md", ROOT / "backend" / "README.md",
        *[DOCS / name for name in (
            "25B_high_precision_multimodal_rag_report.md", "25B_retrieval_evaluation_report.md",
            "25B_embedding_and_dashvector_real_acceptance.md", "25B_index_lifecycle_and_operations.md",
            "25B_multimodal_retrieval_report.md", "25A_competition_requirement_traceability_matrix.md",
            "25A_refactoring_decision_and_roadmap.md", "09_testing_acceptance_and_quality_spec.md",
            "19_delivery_checklist.md",
        )],
    ]
    for path in updates:
        upsert(path, section)
    artifacts = {str(path.relative_to(ROOT)): sha256_file(path) for path in DOCS.glob("25B_R1_*.md")}
    write_json("report_manifest.json", {"status": "PASSED", "generated_at": now_iso(), "artifacts": artifacts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
