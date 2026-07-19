from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, MaintenanceTask, UploadedMedia, User


class MediaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, media: UploadedMedia) -> UploadedMedia:
        self.db.add(media)
        self.db.flush()
        self.db.refresh(media)
        return media

    def get_by_id(self, media_id: UUID) -> UploadedMedia | None:
        return self.db.get(UploadedMedia, media_id)

    def get_by_source_hash(self, source_sha256: str, uploaded_by: UUID) -> UploadedMedia | None:
        statement = (
            select(UploadedMedia)
            .where(
                UploadedMedia.uploaded_by == uploaded_by,
                UploadedMedia.status != "archived",
                UploadedMedia.metadata_json["source_sha256"].astext == source_sha256,
            )
            .order_by(UploadedMedia.created_at.asc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_by_ids(self, media_ids: list[UUID]) -> list[UploadedMedia]:
        if not media_ids:
            return []
        statement = select(UploadedMedia).where(UploadedMedia.id.in_(media_ids))
        items = list(self.db.scalars(statement))
        item_map = {item.id: item for item in items}
        return [item_map[media_id] for media_id in media_ids if media_id in item_map]

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def get_task(self, task_id: UUID) -> MaintenanceTask | None:
        return self.db.get(MaintenanceTask, task_id)

    def get_user(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def link_to_qa(self, media_items: list[UploadedMedia], trace_id: str) -> None:
        for media in media_items:
            media.qa_trace_id = trace_id
            self.db.add(media)

    def link_to_task(self, media_items: list[UploadedMedia], task_id: UUID) -> None:
        for media in media_items:
            media.task_id = task_id
            self.db.add(media)

    def list_media(
        self,
        *,
        media_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        device_id: UUID | None = None,
        task_id: UUID | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UploadedMedia], int]:
        filters = []
        if media_type:
            filters.append(UploadedMedia.media_type == media_type)
        if manufacturer:
            filters.append(UploadedMedia.manufacturer == manufacturer)
        if product_series:
            filters.append(UploadedMedia.product_series == product_series)
        if device_type:
            filters.append(UploadedMedia.device_type == device_type)
        if device_id:
            filters.append(UploadedMedia.device_id == device_id)
        if task_id:
            filters.append(UploadedMedia.task_id == task_id)
        if fault_type:
            filters.append(UploadedMedia.metadata_json["fault_type"].astext == fault_type)
        if alarm_code:
            filters.append(UploadedMedia.metadata_json["alarm_code"].astext.ilike(f"%{alarm_code}%"))
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    UploadedMedia.file_name.ilike(pattern),
                    UploadedMedia.original_file_name.ilike(pattern),
                    UploadedMedia.description.ilike(pattern),
                    UploadedMedia.ocr_text.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(UploadedMedia)
        list_statement = select(UploadedMedia).order_by(UploadedMedia.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        media_items = list(
            self.db.scalars(
                list_statement.offset((page - 1) * page_size).limit(page_size)
            )
        )
        return media_items, total
