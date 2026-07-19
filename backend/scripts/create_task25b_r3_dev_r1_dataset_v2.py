from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from task25b_r3_dev_common import ROOT, now_iso


SOURCE = "task25b_r2_u3_r3_dev_zh_v1"
TARGET = "task25b_r3_dev_r1_zh_v2"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def _stable_payload(case: RetrievalEvaluationCase) -> dict:
    return {
        "name": case.name, "category": case.category, "query_text": case.query_text,
        "expected_document_ids": case.expected_document_ids or [], "expected_chunk_ids": case.expected_chunk_ids or [],
        "expected_media_ids": case.expected_media_ids or [], "required_filters": case.required_filters or {},
        "excluded_document_ids": case.excluded_document_ids or [], "difficulty": case.difficulty,
        "dataset_split": case.dataset_split, "review_status": case.review_status, "source_type": case.source_type,
        "metadata_json": case.metadata_json or {},
    }


def main() -> None:
    with SessionLocal() as db:
        existing = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == TARGET
        ).order_by(RetrievalEvaluationCase.created_at)))
        if existing:
            cases = existing
            if any((item.metadata_json or {}).get("test_v2_frozen") for item in cases):
                raise SystemExit("v2 dataset is frozen and cannot be changed")
            chunk_ids = [value for case in cases for value in (case.expected_chunk_ids or [])]
            chunks = {str(item.id): item for item in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))}
            doc_ids = {item.document_id for item in chunks.values()}
            documents = {str(item.id): item for item in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids)))}
            for case in cases:
                if case.category == "no_answer":
                    continue
                metadata = dict(case.metadata_json or {})
                chunk = chunks.get(str((case.expected_chunk_ids or [None])[0]))
                document = documents.get(str(chunk.document_id)) if chunk else None
                if not chunk or not document:
                    continue
                if not (metadata.get("required_model") or metadata.get("required_alarm_identifier") or metadata.get("required_fault_name")):
                    section = chunk.section_title or (chunk.metadata_json or {}).get("source_locator") or document.title
                    case.query_text = f"根据华为官方 {document.product_series or ''} 资料《{document.title}》中“{section}”章节，说明相关操作、原因或注意事项。"
                    metadata["label_correction"] = "grounded_document_section_query"
                    case.metadata_json = metadata
                case.required_filters = {
                    "manufacturer": "huawei", "product_series": document.product_series,
                    "device_type": document.device_type,
                }
                db.add(case)
            db.commit()
        else:
            source = list(db.scalars(select(RetrievalEvaluationCase).where(
                RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == SOURCE
            ).order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.created_at)))
            if len(source) != 150:
                raise SystemExit(f"expected 150 v1 cases, got {len(source)}")
            chunk_ids = [value for case in source for value in (case.expected_chunk_ids or [])]
            chunks = {str(item.id): item for item in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))}
            doc_ids = {item.document_id for item in chunks.values()}
            documents = {str(item.id): item for item in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids)))}
            ordered = sorted(source, key=lambda item: hashlib.sha256(str(item.id).encode()).hexdigest())
            cases = []
            for index, old in enumerate(ordered):
                split = "train" if index < 90 else "dev" if index < 120 else "test_v2"
                query = old.query_text
                category = old.category
                metadata = dict(old.metadata_json or {})
                expected_chunk = chunks.get(str((old.expected_chunk_ids or [None])[0]))
                document = documents.get(str(expected_chunk.document_id)) if expected_chunk else None
                correction = None
                if category == "device_model_query" and document:
                    doc_meta = document.metadata_json or {}
                    models = doc_meta.get("device_models") or doc_meta.get("applicable_device_models") or []
                    model = str((models[0] if models else document.model or document.product_series or "")).strip()
                    if model:
                        query = f"华为 {model} 设备中，{expected_chunk.section_title or document.title} 应如何处理？"
                        metadata["required_model"] = model
                        correction = "grounded_model_query"
                    else:
                        category = "maintenance"
                        correction = "model_category_reclassified_no_grounded_model"
                if category == "fault_code_query" and expected_chunk:
                    codes = re.findall(r"(?<!\d)(?:[A-Z]{1,4}[-_]?)?\d{3,6}(?!\d)", expected_chunk.content or "", re.I)
                    codes = [value for value in codes if not (1900 <= int(re.sub(r"\D", "", value) or 0) <= 2100)]
                    if codes:
                        alarm = codes[0].upper()
                        query = f"华为设备出现告警 {alarm} 时，应如何排查和处理？"
                        metadata["required_alarm_identifier"] = alarm
                        correction = "grounded_alarm_code_query"
                    else:
                        fault_name = (expected_chunk.section_title or "").strip()
                        if fault_name:
                            query = f"华为设备出现“{fault_name}”告警或故障时，应如何处理？"
                            metadata["required_fault_name"] = fault_name
                            metadata["fault_name_only"] = True
                            correction = "grounded_fault_name_query"
                        else:
                            category = "fault_symptom"
                            correction = "alarm_category_reclassified_no_grounded_identifier"
                metadata.update({
                    "dataset_version": TARGET, "source_dataset_version": SOURCE, "source_case_id": str(old.id),
                    "engineering_verified": True, "expert_verified": False, "second_reviewed": False,
                    "label_correction": correction, "test_v2_frozen": False,
                })
                cases.append(RetrievalEvaluationCase(
                    name=f"R1-v2-{index+1:03d}-{old.name}", category=category, query_text=query,
                    expected_document_ids=list(old.expected_document_ids or []),
                    expected_chunk_ids=list(old.expected_chunk_ids or []), expected_media_ids=list(old.expected_media_ids or []),
                    required_filters={
                        **(old.required_filters or {}), "manufacturer": "huawei",
                        **({"device_type": document.device_type} if document else {}),
                        **({"product_series": document.product_series} if document and document.product_series else {}),
                    },
                    excluded_document_ids=list(old.excluded_document_ids or []), difficulty=old.difficulty,
                    dataset_split=split, review_status="engineering_verified", source_type="engineering_candidate",
                    metadata_json=metadata, created_by=old.created_by, reviewed_by=None,
                ))
            db.add_all(cases); db.commit()

        stable = [_stable_payload(case) for case in sorted(cases, key=lambda item: item.name)]
        digest = hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        splits = Counter(item.dataset_split for item in cases)
        corrections = Counter((item.metadata_json or {}).get("label_correction") for item in cases if (item.metadata_json or {}).get("label_correction"))
        payload = {"generated_at": now_iso(), "dataset_version": TARGET, "source_dataset_version": SOURCE,
                   "case_count": len(cases), "splits": dict(splits), "dataset_sha256": digest,
                   "corrections": dict(corrections), "expert_verified": False, "idempotent": bool(existing)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dataset_v2_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
