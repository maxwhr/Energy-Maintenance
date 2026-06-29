from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KGCandidate,
    KGExtractionRun,
    KnowledgeChunk,
    KnowledgeContribution,
    KnowledgeDocument,
    SOPTemplate,
    UploadedMedia,
    User,
)
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.services.kg_rule_extractor import KGExtractionSource, KGRuleExtractor


class KGExtractionServiceError(ValueError):
    pass


class KGExtractionPermissionError(PermissionError):
    pass


REVIEWER_ROLES = {"admin", "expert"}


class KGExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeGraphRepository(db)
        self.extractor = KGRuleExtractor()

    def extract_from_document(
        self,
        document_id: UUID,
        *,
        current_user: User,
        max_chunks: int = 80,
    ) -> dict[str, Any]:
        self._require_reviewer(current_user)
        document = self.db.get(KnowledgeDocument, document_id)
        if not document or document.status == "archived":
            raise KGExtractionServiceError("Knowledge document not found")
        if document.parse_status != "parsed" or document.review_status != "approved":
            raise KGExtractionServiceError("Only approved and parsed documents can be used for graph extraction")
        chunks = list(
            self.db.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.document_id == document.id, KnowledgeChunk.status == "active")
                .order_by(KnowledgeChunk.chunk_index.asc())
                .limit(max_chunks)
            )
        )
        if not chunks:
            raise KGExtractionServiceError("Document has no active knowledge chunks")
        sources = [
            KGExtractionSource(
                source_type="knowledge_document",
                source_id=document.id,
                text=chunk.content,
                manufacturer=document.manufacturer,
                product_series=document.product_series,
                device_type=document.device_type,
                document_id=document.id,
                chunk_id=chunk.id,
            )
            for chunk in chunks
        ]
        return self._create_run_and_candidates(
            source_type="knowledge_document",
            source_id=document.id,
            sources=sources,
            current_user=current_user,
            metadata={"document_title": document.title, "chunk_count": len(chunks)},
        )

    def extract_from_contribution(
        self,
        contribution_id: UUID,
        *,
        current_user: User,
    ) -> dict[str, Any]:
        contribution = self.db.get(KnowledgeContribution, contribution_id)
        if not contribution:
            raise KGExtractionServiceError("Knowledge contribution not found")
        if current_user.role == "engineer" and contribution.submitted_by != current_user.id:
            raise KGExtractionPermissionError("Engineers can only extract graph candidates from their own contributions")
        if current_user.role not in {"admin", "expert", "engineer"}:
            raise KGExtractionPermissionError("Permission denied")
        if contribution.review_status not in {"approved", "converted"}:
            raise KGExtractionServiceError("Only approved or converted contributions can be used for graph extraction")
        source = KGExtractionSource(
            source_type="knowledge_contribution",
            source_id=contribution.id,
            text=contribution.content,
            manufacturer=contribution.manufacturer,
            product_series=contribution.product_series,
            device_type=contribution.device_type,
            contribution_id=contribution.id,
        )
        return self._create_run_and_candidates(
            source_type="knowledge_contribution",
            source_id=contribution.id,
            sources=[source],
            current_user=current_user,
            metadata={"contribution_title": contribution.title},
        )

    def extract_from_record(
        self,
        record_type: str,
        record_id: UUID,
        *,
        current_user: User,
    ) -> dict[str, Any]:
        self._require_reviewer(current_user)
        normalized_type = record_type.strip().lower()
        source = self._source_from_record(normalized_type, record_id)
        if not source:
            raise KGExtractionServiceError("Supported source record not found")
        return self._create_run_and_candidates(
            source_type=normalized_type,
            source_id=record_id,
            sources=[source],
            current_user=current_user,
            metadata={"record_type": normalized_type},
        )

    def _source_from_record(self, record_type: str, record_id: UUID) -> KGExtractionSource | None:
        if record_type in {"diagnosis", "diagnosis_record"}:
            record = self.db.get(DiagnosisRecord, record_id)
            if not record:
                return None
            text = "\n".join(
                [
                    record.fault_description or "",
                    record.alarm_info or "",
                    " ".join(record.possible_causes or []),
                    " ".join(record.inspection_steps or []),
                    " ".join(record.safety_notes or []),
                    " ".join(record.recommended_actions or []),
                ]
            )
            return KGExtractionSource(
                source_type="diagnosis_record",
                source_id=record.id,
                text=text,
                manufacturer=record.manufacturer,
                product_series=record.product_series,
                device_type=record.device_type,
                diagnosis_trace_id=record.trace_id,
            )
        if record_type == "maintenance_record":
            record = self.db.get(DeviceMaintenanceRecord, record_id)
            if not record:
                return None
            device = record.device
            text = "\n".join(
                [
                    record.fault_description or "",
                    record.root_cause or "",
                    record.repair_action or "",
                    record.replaced_parts or "",
                    record.verification_result or "",
                ]
            )
            return KGExtractionSource(
                source_type="maintenance_record",
                source_id=record.id,
                text=text,
                manufacturer=getattr(device, "manufacturer", None),
                product_series=getattr(device, "product_series", None),
                device_type=getattr(device, "device_type", "pv_inverter") or "pv_inverter",
                diagnosis_trace_id=record.diagnosis_trace_id,
                task_id=record.task_id,
                maintenance_record_id=record.id,
            )
        if record_type == "sop_template":
            record = self.db.get(SOPTemplate, record_id)
            if not record or record.status == "archived":
                return None
            text = "\n".join(
                [
                    record.title,
                    record.compliance_notes or "",
                    " ".join(str(item) for item in record.steps or []),
                    " ".join(str(item) for item in record.safety_requirements or []),
                    " ".join(str(item) for item in record.tools_required or []),
                    " ".join(str(item) for item in record.materials_required or []),
                ]
            )
            return KGExtractionSource(
                source_type="sop_template",
                source_id=record.id,
                text=text,
                manufacturer=record.manufacturer,
                product_series=record.product_series,
                device_type=record.device_type,
            )
        if record_type in {"media", "uploaded_media"}:
            record = self.db.get(UploadedMedia, record_id)
            if not record or record.status == "archived":
                return None
            text = "\n".join([record.description or "", record.ocr_text or "", str(record.metadata_json or {})])
            return KGExtractionSource(
                source_type="uploaded_media",
                source_id=record.id,
                text=text,
                manufacturer=record.manufacturer,
                product_series=record.product_series,
                device_type=record.device_type,
                media_id=record.id,
                task_id=record.task_id,
            )
        return None

    def _create_run_and_candidates(
        self,
        *,
        source_type: str,
        source_id: UUID | None,
        sources: list[KGExtractionSource],
        current_user: User,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        run = KGExtractionRun(
            source_type=source_type,
            source_id=source_id,
            extractor=self.extractor.extractor_name,
            status="running",
            started_at=datetime.now(timezone.utc),
            created_by=current_user.id,
            metadata_json=metadata,
        )
        try:
            run = self.repository.create_run(run)
            raw_candidates = self.extractor.extract(sources)
            candidates = [
                KGCandidate(
                    run_id=run.id,
                    candidate_type=item["candidate_type"],
                    payload_json=item["payload"],
                    status="pending",
                    confidence=float(item.get("confidence") or 0.6),
                    evidence_text=item.get("evidence_text"),
                )
                for item in raw_candidates
            ]
            self.repository.create_candidates(candidates)
            run.status = "completed"
            run.candidate_count = len(candidates)
            run.finished_at = datetime.now(timezone.utc)
            self.repository.update_run(run)
            self.db.commit()
            self.db.refresh(run)
            refreshed_candidates, _ = self.repository.list_candidates(run_id=run.id, page=1, page_size=500)
            return {"run": run, "candidates": refreshed_candidates}
        except SQLAlchemyError as exc:
            self.db.rollback()
            failed_run = KGExtractionRun(
                source_type=source_type,
                source_id=source_id,
                extractor=self.extractor.extractor_name,
                status="failed",
                error_summary=str(exc)[:1000],
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                created_by=current_user.id,
                metadata_json=metadata,
            )
            self.repository.create_run(failed_run)
            self.db.commit()
            raise KGExtractionServiceError(f"Knowledge graph extraction failed: {exc}") from exc

    @staticmethod
    def _require_reviewer(current_user: User) -> None:
        if current_user.role not in REVIEWER_ROLES:
            raise KGExtractionPermissionError("Only experts and admins can trigger this graph extraction")
