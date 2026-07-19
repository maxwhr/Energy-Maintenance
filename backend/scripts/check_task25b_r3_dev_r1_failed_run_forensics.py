from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun
from task25b_r3_dev_common import ROOT, now_iso


RUN_ID = UUID("f1941ec2-9878-45a1-b554-8d9f2f2ec911")
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"
OUT.mkdir(parents=True, exist_ok=True)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    with SessionLocal() as db:
        run = db.get(RetrievalEvaluationRun, RUN_ID)
        if run is None:
            raise SystemExit("failed baseline run not found")
        results = list(db.scalars(select(RetrievalEvaluationResult).where(
            RetrievalEvaluationResult.run_id == RUN_ID
        ).order_by(RetrievalEvaluationResult.case_id, RetrievalEvaluationResult.retrieval_mode)))
        case_ids = {item.case_id for item in results}
        cases = {item.id: item for item in db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.id.in_(case_ids)
        ))}
        all_chunk_ids = {_uuid(value) for item in results for value in [
            *(item.ranked_chunk_ids or []), *((cases.get(item.case_id).expected_chunk_ids or []) if cases.get(item.case_id) else [])
        ]}
        all_chunk_ids.discard(None)
        chunks = {item.id: item for item in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(all_chunk_ids)))}
        document_ids = {item.document_id for item in chunks.values()}
        document_ids.update(_uuid(value) for item in results for value in [
            *(item.ranked_document_ids or []), *((cases.get(item.case_id).expected_document_ids or []) if cases.get(item.case_id) else [])
        ])
        document_ids.discard(None)
        documents = {item.id: item for item in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))}

        rows: list[dict] = []
        for result in results:
            case = cases[result.case_id]
            actual_chunk_ids = [str(value) for value in (result.ranked_chunk_ids or [])]
            actual_doc_ids = [str(value) for value in (result.ranked_document_ids or [])]
            result_languages: list[str | None] = []
            result_statuses: list[str | None] = []
            result_current: list[bool] = []
            for value in actual_chunk_ids:
                chunk = chunks.get(_uuid(value))
                document = documents.get(chunk.document_id) if chunk else None
                metadata = document.metadata_json or {} if document else {}
                result_languages.append(metadata.get("normalized_language"))
                result_statuses.append(document.review_status if document else None)
                result_current.append(bool(chunk and chunk.status == "active" and document and document.status == "active"
                                           and not metadata.get("superseded_by_document_id")))
            rows.append({
                "run_id": str(run.id), "dataset_version": run.dataset_version, "case_id": str(case.id),
                "case_name": case.name, "category": case.category, "mode": result.retrieval_mode,
                "query_text": case.query_text, "expected_document_ids": _json(case.expected_document_ids or []),
                "expected_chunk_ids": _json(case.expected_chunk_ids or []), "actual_document_ids": _json(actual_doc_ids),
                "actual_chunk_ids": _json(actual_chunk_ids), "score_breakdown": _json(result.score_breakdown_json or {}),
                "latency_ms": result.latency_ms, "fallback": result.fallback_used,
                "filters": _json(case.required_filters or {}), "result_languages": _json(result_languages),
                "result_document_statuses": _json(result_statuses), "result_current_flags": _json(result_current),
                "error_summary": result.error_summary or "",
            })

        snapshot = {
            "generated_at": now_iso(), "read_only": True, "run_id": str(run.id), "run_status": run.run_status,
            "dataset_version": run.dataset_version, "retrieval_config": run.retrieval_config_json,
            "collection": run.collection_name, "partition": "pilot_r2", "embedding_provider": run.embedding_provider,
            "embedding_model": run.embedding_model, "embedding_dimension": run.embedding_dimension,
            "started_at": run.started_at, "completed_at": run.completed_at, "metrics": run.metrics_json,
            "case_count": len(cases), "result_count": len(results), "mutation_performed": False,
        }

    snapshot_path = OUT / "failed_run_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    csv_path = OUT / "failed_run_case_results.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    source_gate = ROOT / ".runtime" / "task25b_r2_u3_r3_dev" / "chinese_pilot_quality_gate.json"
    hashes = {str(path.relative_to(ROOT)): _sha(path) for path in (snapshot_path, csv_path, source_gate) if path.exists()}
    manifest = {"generated_at": now_iso(), "algorithm": "SHA-256", "run_id": str(RUN_ID), "artifacts": hashes}
    manifest_path = OUT / "failed_run_hash_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = ROOT / "docs" / "25B_R3_DEV_R1_failed_run_forensics_report.md"
    report.write_text(
        "# Task 25B-R3-DEV-R1 失败 Run 取证报告\n\n"
        f"- run：`{RUN_ID}`\n- dataset：`{snapshot['dataset_version']}`\n"
        f"- 状态：`{snapshot['run_status']}`（执行完整但质量门失败）\n"
        f"- cases/results：{snapshot['case_count']}/{snapshot['result_count']}\n"
        f"- Collection/Partition：`{snapshot['collection']}` / `pilot_r2`\n"
        f"- Embedding：`{snapshot['embedding_model']}` / {snapshot['embedding_dimension']}\n"
        "- 取证方式：只读；未修改 run 状态、结果或 metrics。\n"
        "- 完整逐 case/mode 排名、标签、分数、延迟、fallback、过滤器和结果状态见 CSV。\n",
        encoding="utf-8",
    )
    print(_json({"status": "PASSED", "run_id": str(RUN_ID), "cases": len(cases), "results": len(rows), "artifacts": 4}))


if __name__ == "__main__":
    main()
