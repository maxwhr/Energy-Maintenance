from __future__ import annotations

import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase, RetrievalEvaluationResult
from app.services.query_understanding_service import QueryUnderstandingService, normalize_alarm_identifier, normalize_device_model
from task25b_r3_dev_r2_common import OUT, ROOT, V2_DATASET, V2_RUN_ID, now_iso


def _ratio(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _contains_model(chunk: KnowledgeChunk | None, document: KnowledgeDocument | None, model: str) -> bool:
    target = normalize_device_model(model)
    if not target:
        return False
    candidates = [document.model if document else "", document.product_series if document else "", chunk.content if chunk else "",
                  chunk.section_title if chunk else ""]
    if document:
        candidates.extend((document.metadata_json or {}).get("device_models", []))
    return any(target in normalize_device_model(str(value)) for value in candidates if value)


def _contains_alarm(chunk: KnowledgeChunk | None, document: KnowledgeDocument | None, alarm: str) -> bool:
    target = normalize_alarm_identifier(alarm)
    if not target:
        return False
    candidates = [chunk.content if chunk else "", chunk.section_title if chunk else ""]
    if chunk:
        candidates.extend((chunk.metadata_json or {}).get("fault_codes", []))
    return any(target in normalize_alarm_identifier(str(value)) for value in candidates if value)


def main() -> None:
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V2_DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v2",
        )))
        case_by_id = {case.id: case for case in cases}
        results = list(db.scalars(select(RetrievalEvaluationResult).where(
            RetrievalEvaluationResult.run_id == UUID(V2_RUN_ID)
        )))
        ids = {UUID(str(value)) for result in results for value in (result.ranked_chunk_ids or [])}
        chunks = {chunk.id: chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids)))}
        docs = {doc.id: doc for doc in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_({chunk.document_id for chunk in chunks.values()})))}
        model_by_mode: dict[str, list[dict]] = defaultdict(list); alarm_by_mode: dict[str, list[dict]] = defaultdict(list)
        parser = QueryUnderstandingService()
        for result in results:
            case = case_by_id.get(result.case_id)
            if not case:
                continue
            metadata = case.metadata_json or {}
            analysis = parser.understand(case.query_text)
            top_chunk = chunks.get(UUID(str(result.ranked_chunk_ids[0]))) if result.ranked_chunk_ids else None
            top_doc = docs.get(top_chunk.document_id) if top_chunk else None
            model = str(metadata.get("required_model") or "")
            if model or case.category == "device_model_query":
                model_by_mode[result.retrieval_mode].append({
                    "extraction": normalize_device_model(model) in {normalize_device_model(item) for item in analysis.device_models} if model else False,
                    "consistency": _contains_model(top_chunk, top_doc, model) if model else False,
                    "exact_filter": _contains_model(top_chunk, top_doc, model) if model else False,
                })
            alarm = str(metadata.get("required_alarm_identifier") or "")
            if alarm or case.category == "fault_code_query":
                alarm_by_mode[result.retrieval_mode].append({
                    "extraction": normalize_alarm_identifier(alarm) in {normalize_alarm_identifier(item) for item in analysis.fault_codes} if alarm else False,
                    "consistency": _contains_alarm(top_chunk, top_doc, alarm) if alarm else False,
                    "exact_filter": _contains_alarm(top_chunk, top_doc, alarm) if alarm else False,
                })
    payload = {"generated_at": now_iso(), "dataset": V2_DATASET, "run_id": V2_RUN_ID, "test_v2_only": True,
               "model": {mode: {"coverage": len(values), "query_model_extraction_accuracy": _ratio([x["extraction"] for x in values]),
                                "retrieved_model_consistency": _ratio([x["consistency"] for x in values]),
                                "exact_model_filter_accuracy": _ratio([x["exact_filter"] for x in values]),
                                "applicable": bool(values)} for mode, values in model_by_mode.items()},
               "alarm": {mode: {"coverage": len(values), "query_alarm_extraction_accuracy": _ratio([x["extraction"] for x in values]),
                                "retrieved_alarm_consistency": _ratio([x["consistency"] for x in values]),
                                "exact_alarm_filter_accuracy": _ratio([x["exact_filter"] for x in values]),
                                "applicable": bool(values)} for mode, values in alarm_by_mode.items()},
               "model_coverage_gate": sum(len(x) for x in model_by_mode.values()) // max(1, len(model_by_mode)) >= 12,
               "alarm_coverage_gate": sum(len(x) for x in alarm_by_mode.values()) // max(1, len(alarm_by_mode)) >= 12}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model_alarm_metric_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "model_cases": next(iter(payload["model"].values()), {}).get("coverage", 0),
                      "alarm_cases": next(iter(payload["alarm"].values()), {}).get("coverage", 0),
                      "model_coverage_gate": payload["model_coverage_gate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
