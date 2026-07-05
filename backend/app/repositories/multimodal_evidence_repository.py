from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import UploadedMedia
from app.models.multimodal_evidence import (
    MediaAIAnalysis,
    MediaEvidenceLink,
    MediaOCRResult,
    MediaProcessingJob,
)


class MultimodalEvidenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_media(self, media_id: UUID) -> UploadedMedia | None:
        return self.db.get(UploadedMedia, media_id)

    def create_job(self, job: MediaProcessingJob) -> MediaProcessingJob:
        self.db.add(job)
        self.db.flush()
        self.db.refresh(job)
        return job

    def update_job(self, job: MediaProcessingJob) -> MediaProcessingJob:
        self.db.add(job)
        self.db.flush()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: UUID) -> MediaProcessingJob | None:
        return self.db.get(MediaProcessingJob, job_id)

    def list_jobs_by_media(
        self,
        media_id: UUID,
        *,
        job_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MediaProcessingJob], int]:
        filters = [MediaProcessingJob.media_id == media_id]
        if job_type:
            filters.append(MediaProcessingJob.job_type == job_type)
        if status:
            filters.append(MediaProcessingJob.status == status)
        count_statement = select(func.count()).select_from(MediaProcessingJob).where(*filters)
        list_statement = (
            select(MediaProcessingJob)
            .where(*filters)
            .order_by(MediaProcessingJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(list_statement)), self.db.scalar(count_statement) or 0

    def create_ocr_result(self, result: MediaOCRResult) -> MediaOCRResult:
        self.db.add(result)
        self.db.flush()
        self.db.refresh(result)
        return result

    def get_ocr_result(self, result_id: UUID) -> MediaOCRResult | None:
        return self.db.get(MediaOCRResult, result_id)

    def list_ocr_results(
        self,
        media_id: UUID,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MediaOCRResult], int]:
        filters = [MediaOCRResult.media_id == media_id]
        if status:
            filters.append(MediaOCRResult.status == status)
        count_statement = select(func.count()).select_from(MediaOCRResult).where(*filters)
        list_statement = (
            select(MediaOCRResult)
            .where(*filters)
            .order_by(MediaOCRResult.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(list_statement)), self.db.scalar(count_statement) or 0

    def latest_ocr_result(self, media_id: UUID, *, status: str | None = None) -> MediaOCRResult | None:
        statement = select(MediaOCRResult).where(MediaOCRResult.media_id == media_id)
        if status:
            statement = statement.where(MediaOCRResult.status == status)
        return self.db.scalar(statement.order_by(MediaOCRResult.created_at.desc()).limit(1))

    def create_ai_analysis(self, analysis: MediaAIAnalysis) -> MediaAIAnalysis:
        self.db.add(analysis)
        self.db.flush()
        self.db.refresh(analysis)
        return analysis

    def update_ai_analysis(self, analysis: MediaAIAnalysis) -> MediaAIAnalysis:
        self.db.add(analysis)
        self.db.flush()
        self.db.refresh(analysis)
        return analysis

    def get_ai_analysis(self, analysis_id: UUID) -> MediaAIAnalysis | None:
        return self.db.get(MediaAIAnalysis, analysis_id)

    def list_ai_analyses(
        self,
        media_id: UUID,
        *,
        human_review_status: str | None = None,
        analysis_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MediaAIAnalysis], int]:
        filters = [MediaAIAnalysis.media_id == media_id]
        if human_review_status:
            filters.append(MediaAIAnalysis.human_review_status == human_review_status)
        if analysis_type:
            filters.append(MediaAIAnalysis.analysis_type == analysis_type)
        count_statement = select(func.count()).select_from(MediaAIAnalysis).where(*filters)
        list_statement = (
            select(MediaAIAnalysis)
            .where(*filters)
            .order_by(MediaAIAnalysis.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(list_statement)), self.db.scalar(count_statement) or 0

    def latest_ai_analysis(
        self,
        media_id: UUID,
        *,
        human_review_status: str | None = None,
    ) -> MediaAIAnalysis | None:
        statement = select(MediaAIAnalysis).where(MediaAIAnalysis.media_id == media_id)
        if human_review_status:
            statement = statement.where(MediaAIAnalysis.human_review_status == human_review_status)
        return self.db.scalar(statement.order_by(MediaAIAnalysis.created_at.desc()).limit(1))

    def create_evidence_link(self, link: MediaEvidenceLink) -> MediaEvidenceLink:
        self.db.add(link)
        self.db.flush()
        self.db.refresh(link)
        return link

    def list_evidence_links(
        self,
        *,
        media_id: UUID | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MediaEvidenceLink], int]:
        filters = []
        if media_id:
            filters.append(MediaEvidenceLink.media_id == media_id)
        if source_type:
            filters.append(MediaEvidenceLink.source_type == source_type)
        if source_id:
            filters.append(MediaEvidenceLink.source_id == source_id)
        count_statement = select(func.count()).select_from(MediaEvidenceLink)
        list_statement = select(MediaEvidenceLink).order_by(MediaEvidenceLink.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        items = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return items, self.db.scalar(count_statement) or 0
