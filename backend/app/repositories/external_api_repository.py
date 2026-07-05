from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.external_api import (
    ExternalApiCallLog,
    ExternalApiHealthCheck,
    ExternalApiProvider,
    ExternalApiRoute,
)


class ExternalApiRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_provider(self, values: dict) -> ExternalApiProvider:
        existing = self.get_provider(values["provider_code"])
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            self.db.flush()
            self.db.refresh(existing)
            return existing
        provider = ExternalApiProvider(**values)
        self.db.add(provider)
        self.db.flush()
        self.db.refresh(provider)
        return provider

    def get_provider(self, provider_code: str) -> ExternalApiProvider | None:
        return self.db.scalar(
            select(ExternalApiProvider).where(ExternalApiProvider.provider_code == provider_code)
        )

    def list_providers(
        self,
        *,
        provider_type: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> list[ExternalApiProvider]:
        statement = select(ExternalApiProvider).order_by(ExternalApiProvider.provider_code.asc())
        filters = []
        if provider_type:
            filters.append(ExternalApiProvider.provider_type == provider_type)
        if enabled is not None:
            filters.append(ExternalApiProvider.enabled == enabled)
        if status:
            filters.append(ExternalApiProvider.status == status)
        if filters:
            statement = statement.where(*filters)
        return list(self.db.scalars(statement))

    def update_provider(self, provider: ExternalApiProvider) -> ExternalApiProvider:
        self.db.add(provider)
        self.db.flush()
        self.db.refresh(provider)
        return provider

    def upsert_route(self, values: dict) -> ExternalApiRoute:
        existing = self.get_route(values["route_code"])
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            self.db.flush()
            self.db.refresh(existing)
            return existing
        route = ExternalApiRoute(**values)
        self.db.add(route)
        self.db.flush()
        self.db.refresh(route)
        return route

    def get_route(self, route_code: str) -> ExternalApiRoute | None:
        return self.db.scalar(select(ExternalApiRoute).where(ExternalApiRoute.route_code == route_code))

    def find_route(
        self,
        *,
        route_code: str | None = None,
        agent_code: str | None = None,
        tool_name: str | None = None,
        capability: str | None = None,
    ) -> ExternalApiRoute | None:
        if route_code:
            return self.get_route(route_code)

        statement = select(ExternalApiRoute)
        filters = []
        if capability:
            filters.append(ExternalApiRoute.capability == capability)
        if tool_name:
            filters.append(ExternalApiRoute.tool_name == tool_name)
        if agent_code:
            filters.append(or_(ExternalApiRoute.agent_code == agent_code, ExternalApiRoute.agent_code.is_(None)))
        if filters:
            statement = statement.where(*filters)
        return self.db.scalar(statement.order_by(ExternalApiRoute.route_code.asc()).limit(1))

    def list_routes(
        self,
        *,
        agent_code: str | None = None,
        tool_name: str | None = None,
        capability: str | None = None,
    ) -> list[ExternalApiRoute]:
        statement = select(ExternalApiRoute).order_by(ExternalApiRoute.route_code.asc())
        filters = []
        if agent_code:
            filters.append(ExternalApiRoute.agent_code == agent_code)
        if tool_name:
            filters.append(ExternalApiRoute.tool_name == tool_name)
        if capability:
            filters.append(ExternalApiRoute.capability == capability)
        if filters:
            statement = statement.where(*filters)
        return list(self.db.scalars(statement))

    def create_call_log(self, log: ExternalApiCallLog) -> ExternalApiCallLog:
        self.db.add(log)
        self.db.flush()
        self.db.refresh(log)
        return log

    def get_call_log_by_trace_id(self, trace_id: str) -> ExternalApiCallLog | None:
        return self.db.scalar(select(ExternalApiCallLog).where(ExternalApiCallLog.trace_id == trace_id))

    def list_call_logs(
        self,
        *,
        provider_code: str | None = None,
        capability: str | None = None,
        status: str | None = None,
        success: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExternalApiCallLog], int]:
        filters = []
        if provider_code:
            filters.append(ExternalApiCallLog.provider_code == provider_code)
        if capability:
            filters.append(ExternalApiCallLog.capability == capability)
        if status:
            filters.append(ExternalApiCallLog.status == status)
        if success is not None:
            filters.append(ExternalApiCallLog.success == success)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    ExternalApiCallLog.trace_id.ilike(pattern),
                    ExternalApiCallLog.provider_code.ilike(pattern),
                    ExternalApiCallLog.capability.ilike(pattern),
                    ExternalApiCallLog.error_message.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(ExternalApiCallLog)
        list_statement = select(ExternalApiCallLog).order_by(ExternalApiCallLog.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        items = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return items, total

    def create_health_check(self, item: ExternalApiHealthCheck) -> ExternalApiHealthCheck:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_health_checks(
        self,
        *,
        provider_code: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExternalApiHealthCheck], int]:
        filters = []
        if provider_code:
            filters.append(ExternalApiHealthCheck.provider_code == provider_code)
        count_statement = select(func.count()).select_from(ExternalApiHealthCheck)
        list_statement = select(ExternalApiHealthCheck).order_by(ExternalApiHealthCheck.checked_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        items = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return items, total

    def get_call_log_by_id(self, log_id: UUID) -> ExternalApiCallLog | None:
        return self.db.get(ExternalApiCallLog, log_id)
