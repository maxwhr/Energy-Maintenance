from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QueryAwareRetrievalSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "query_aware_retrieval_sessions"

    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("ix_query_aware_sessions_status", "status"),
        Index("ix_query_aware_sessions_expires", "expires_at"),
        Index("ix_query_aware_sessions_created_by", "created_by"),
    )
