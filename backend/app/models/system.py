from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_status", "status"),
    )


class Device(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "devices"

    device_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(32), nullable=False)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    station_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commissioning_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    last_fault_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fault_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    maintenance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    maintenance_tasks: Mapped[list["MaintenanceTask"]] = relationship(back_populates="device")
    maintenance_records: Mapped[list["DeviceMaintenanceRecord"]] = relationship(back_populates="device")
    media_items: Mapped[list["UploadedMedia"]] = relationship(back_populates="device")

    __table_args__ = (
        UniqueConstraint("device_code", name="uq_devices_device_code"),
        Index("ix_devices_manufacturer", "manufacturer"),
        Index("ix_devices_product_series", "product_series"),
        Index("ix_devices_model", "model"),
        Index("ix_devices_device_type", "device_type"),
        Index("ix_devices_status", "status"),
    )
