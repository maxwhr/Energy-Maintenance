from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.system_statistics_repository import SystemStatisticsRepository
from app.schemas.system_statistics import SystemStatistics


class SystemStatisticsService:
    def __init__(self, db: Session):
        self.repository = SystemStatisticsRepository(db)

    def collect(self) -> dict:
        return SystemStatistics(**self.repository.collect()).model_dump(mode="json")
