from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UploadedMedia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_media"

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id"), nullable=True)
    diagnosis_record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("diagnosis_records.id"),
        nullable=True,
    )
    qa_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    device: Mapped["Device | None"] = relationship(back_populates="media_items")
    task: Mapped["MaintenanceTask | None"] = relationship()
    diagnosis_record: Mapped["DiagnosisRecord | None"] = relationship()
    uploader: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("ix_uploaded_media_device_id", "device_id"),
        Index("ix_uploaded_media_task_id", "task_id"),
        Index("ix_uploaded_media_diagnosis_record_id", "diagnosis_record_id"),
        Index("ix_uploaded_media_media_type", "media_type"),
        Index("ix_uploaded_media_status", "status"),
        Index("ix_uploaded_media_qa_trace_id", "qa_trace_id"),
    )
