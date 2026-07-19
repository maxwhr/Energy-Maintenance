from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QueryAwareRetrievalSession


class QueryAwareRetrievalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, conversation_id: str, *, created_by) -> QueryAwareRetrievalSession | None:
        return self.db.scalar(select(QueryAwareRetrievalSession).where(
            QueryAwareRetrievalSession.conversation_id == conversation_id,
            QueryAwareRetrievalSession.created_by == created_by,
        ))

    def get_active(self, conversation_id: str, *, created_by) -> QueryAwareRetrievalSession | None:
        now = datetime.now(timezone.utc)
        return self.db.scalar(select(QueryAwareRetrievalSession).where(
            QueryAwareRetrievalSession.conversation_id == conversation_id,
            QueryAwareRetrievalSession.created_by == created_by,
            QueryAwareRetrievalSession.status == "active",
            QueryAwareRetrievalSession.expires_at > now,
        ))

    def save(self, item: QueryAwareRetrievalSession) -> QueryAwareRetrievalSession:
        self.db.add(item)
        self.db.flush()
        return item
