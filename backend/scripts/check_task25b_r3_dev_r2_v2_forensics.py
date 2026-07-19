from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun
from task25b_r3_dev_r2_common import OUT, V2_DATASET, V2_RUN_ID, file_hash, jaccard, kendall_like, now_iso, relevance_sets, rank_metrics, section_key


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        run = db.get(RetrievalEvaluationRun, UUID(V2_RUN_ID))
        if run is None or run.dataset_version != V2_DATASET:
            raise SystemExit("frozen v2 run was not found")
        results = list(db.scalars(select(RetrievalEvaluationResult).where(
            RetrievalEvaluationResult.run_id == run.id
        ).order_by(RetrievalEvaluationResult.case_id, RetrievalEvaluationResult.retrieval_mode)))
        case_ids = {result.case_id for result in results}
        cases = {case.id: case for case in db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.id.in_(case_ids)))}
        all_chunk_ids = {_uuid(value) for case in cases.values() for value in (case.expected_chunk_ids or [])}
        all_chunk_ids.update(_uuid(value) for result in results for value in (result.ranked_chunk_ids or []))
        all_chunk_ids.discard(None)
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(all_chunk_ids)))}
        document_ids = {chunk.document_id for chunk in chunks.values()}
        documents = {str(doc.id): doc for doc in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))}

        by_case: dict[UUID, dict[str, RetrievalEvaluationResult]] = defaultdict(dict)
        for result in results:
            by_case[result.case_id][result.retrieval_mode] = result
        metric_rows, cardinality_rows, overlaps = [], [], {}
        for case_id, by_mode in by_case.items():
            case = cases[case_id]
            relevance = relevance_sets(case, chunks, documents)
            ranked = {mode: [str(value) for value in (item.ranked_chunk_ids or [])] for mode, item in by_mode.items()}
            row = {"case_id": str(case_id), "category": case.category,
                   "query_hash": __import__("hashlib").sha256(case.query_text.encode("utf-8")).hexdigest(),
                   "expected_document_count": len(relevance["documents"]), "expected_section_count": len(relevance["sections"]),
                   "expected_chunk_count": len(relevance["chunks"]),
                   "max_possible_precision_at_5": min(5, len(relevance["chunks"])) / 5,
                   "raw_precision_at_5": (by_mode.get("adaptive").precision_at_5 if by_mode.get("adaptive") else 0.0)}
            for mode in ("keyword", "vector", "hybrid", "adaptive"):
                result = by_mode.get(mode)
                values = ranked.get(mode, [])
                metrics = rank_metrics(values, relevance["chunks"])
                row[f"{mode}_result_count"] = len(values)
                row[f"{mode}_relevant_count_at_5"] = sum(value in relevance["chunks"] for value in values[:5])
                row[f"{mode}_hit_at_1"] = metrics["hit_at_1"]
                row[f"{mode}_hit_at_5"] = metrics["hit_at_5"]
                row[f"{mode}_reciprocal_rank"] = metrics["reciprocal_rank"]
                row[f"{mode}_chunk_level_rank"] = metrics["first_rank"]
                doc_ranked = [str(chunks[value].document_id) for value in values if value in chunks]
                sec_ranked = [section_key(chunks.get(value), documents.get(str(chunks[value].document_id))) for value in values if value in chunks]
                row[f"{mode}_document_level_rank"] = rank_metrics(doc_ranked, relevance["documents"])["first_rank"]
                row[f"{mode}_section_level_rank"] = rank_metrics(sec_ranked, relevance["sections"])["first_rank"]
                if result:
                    diagnostics = (result.score_breakdown_json or {}).get("_diagnostics") or {}
                    row[f"{mode}_actual_route"] = diagnostics.get("actual_route")
                    row[f"{mode}_fallback"] = bool(diagnostics.get("fallback_used"))
            metric_rows.append(row)
            cardinality_rows.append({key: row[key] for key in (
                "case_id", "category", "expected_document_count", "expected_section_count", "expected_chunk_count", "max_possible_precision_at_5")})
            overlaps[str(case_id)] = {
                "candidate_jaccard": {f"{left}_{right}": round(jaccard(ranked.get(left, []), ranked.get(right, [])), 6)
                                      for left, right in (("keyword", "vector"), ("keyword", "hybrid"), ("keyword", "adaptive"), ("vector", "adaptive"))},
                "mode_rank_correlation": {f"{left}_{right}": kendall_like(ranked.get(left, []), ranked.get(right, []))
                                          for left, right in (("keyword", "vector"), ("keyword", "hybrid"), ("keyword", "adaptive"), ("vector", "adaptive"))},
            }
        snapshot = {"generated_at": now_iso(), "read_only": True, "mutation_performed": False,
                    "run_id": str(run.id), "run_status": run.run_status, "dataset_version": run.dataset_version,
                    "collection": run.collection_name, "retrieval_config": run.retrieval_config_json,
                    "embedding_model": run.embedding_model, "embedding_dimension": run.embedding_dimension,
                    "case_count": len(cases), "result_count": len(results), "metrics": run.metrics_json}

    snapshot_path = OUT / "v2_snapshot.json"; snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    for path, rows in ((OUT / "v2_case_metrics.csv", metric_rows), (OUT / "v2_relevance_cardinality.csv", cardinality_rows)):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["case_id"]); writer.writeheader(); writer.writerows(rows)
    overlap_path = OUT / "v2_mode_overlap.json"; overlap_path.write_text(json.dumps(overlaps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = OUT / "v2_hash_manifest.json"
    manifest_path.write_text(json.dumps({"generated_at": now_iso(), "algorithm": "SHA-256", "read_only": True, "run_id": V2_RUN_ID,
                                         "artifacts": {path.name: file_hash(path) for path in (snapshot_path, OUT / "v2_case_metrics.csv", OUT / "v2_relevance_cardinality.csv", overlap_path)}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "run_id": V2_RUN_ID, "cases": len(metric_rows), "results": len(results), "mutation_performed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
