from __future__ import annotations

from uuid import UUID

from app.core.config import get_settings
from app.services.external_api_gateway import ExternalApiGateway, ExternalApiGatewayError
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool, json_safe
from app.services.media_service import MediaService
from app.schemas.multimodal_evidence import MediaProcessingJobCreate
from app.services.multimodal_evidence_service import MultimodalEvidenceService, MultimodalEvidenceServiceError


class MediaLookupTool(BaseAgentTool):
    tool_name = "media_lookup"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        service = MediaService(context.db)
        if context.media_ids:
            media_items = service.resolve_media_items(context.media_ids, device_id=context.device_id)
            items = [service.media_payload(item) for item in media_items]
            summaries = self._media_summaries(context)
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Resolved {len(items)} media items.",
                data={"items": json_safe(items), "total": len(items), "multimodal_summaries": summaries},
            )

        result = service.list_media(
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            device_type=payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            device_id=context.device_id,
            fault_type=payload.get("fault_type") or context.context.get("fault_type"),
            alarm_code=payload.get("alarm_code") or context.context.get("alarm_code"),
            keyword=payload.get("keyword"),
            page=1,
            page_size=self.bounded_int(payload.get("page_size"), default=5, minimum=1, maximum=20),
        )
        items = [service.media_payload(item) for item in result.get("items", [])]
        summaries = self._media_summaries_for_items(context, [item.get("id") for item in items if item.get("id")])
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Media lookup returned {len(items)} items.",
            data={
                "items": json_safe(items),
                "total": result.get("total", 0),
                "page": 1,
                "multimodal_summaries": summaries,
            },
        )

    def _media_summaries(self, context: AgentToolExecutionContext) -> dict:
        return self._media_summaries_for_items(context, [str(item) for item in context.media_ids])

    @staticmethod
    def _media_summaries_for_items(context: AgentToolExecutionContext, media_ids: list[str]) -> dict:
        service = MultimodalEvidenceService(context.db)
        summaries: dict[str, dict] = {}
        for media_id in media_ids:
            try:
                summary = service.get_media_multimodal_summary(UUID(str(media_id))).model_dump(mode="json")
            except (MultimodalEvidenceServiceError, ValueError, TypeError):
                continue
            summaries[str(media_id)] = {
                "job_count": len(summary.get("jobs", [])),
                "ocr_result_count": len(summary.get("ocr_results", [])),
                "analysis_count": len(summary.get("analyses", [])),
                "evidence_link_count": len(summary.get("evidence_links", [])),
                "latest_ocr_status": summary.get("latest_ocr_status"),
                "latest_analysis_status": summary.get("latest_analysis_status"),
                "machine_result_boundary": summary.get("machine_result_boundary"),
            }
        return summaries


class MediaOCRTool(BaseAgentTool):
    tool_name = "media_ocr"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        service = MediaService(context.db)
        settings = get_settings()
        media_items = service.resolve_media_items(context.media_ids, device_id=context.device_id) if context.media_ids else []
        evidence_service = MultimodalEvidenceService(context.db)
        center_context = []
        job_statuses = []
        for media_id in context.media_ids:
            latest = evidence_service.latest_ocr_context(media_id)
            if latest:
                center_context.append(latest)
            else:
                job_status = evidence_service.latest_job_status(media_id, job_type="ocr")
                if job_status:
                    job_statuses.append(job_status)
        if center_context:
            real_count = sum(
                1
                for item in center_context
                if ((item.get("raw_result_json") or {}).get("real_external_api_used") is True)
            )
            mock_count = sum(
                1
                for item in center_context
                if ((item.get("raw_result_json") or {}).get("mocked") is True)
            )
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Found {len(center_context)} OCR results from multimodal evidence center.",
                data={
                    "ocr_context": json_safe(center_context),
                    "ocr_enabled": settings.OCR_ENABLED,
                    "source": "real_ocr_results" if real_count else "mocked_ocr_results" if mock_count else "media_ocr_results",
                    "provider_mode": "real" if real_count else "mock" if mock_count else "fallback",
                    "external_api_called": bool(real_count),
                    "real_result_count": real_count,
                    "mock_result_count": mock_count,
                    "machine_result_boundary": "OCR evidence is auxiliary and requires human review.",
                },
            )
        existing_context = service.ocr_context(media_items)
        if existing_context:
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Found existing OCR text for {len(existing_context)} media items.",
                data={"ocr_context": json_safe(existing_context), "ocr_enabled": settings.OCR_ENABLED},
            )
        if payload.get("mock_run") and context.media_ids:
            try:
                for media_id in context.media_ids:
                    evidence_service.create_processing_job(
                        media_id,
                        MediaProcessingJobCreate(
                            job_type="ocr",
                            provider_code=payload.get("provider_code"),
                            capability=payload.get("capability") or "ocr",
                            mock_run=True,
                            dry_run=False,
                            agent_run_id=context.run_id,
                            input_summary={
                                "source": "agent_tool",
                                "tool_name": self.tool_name,
                                "media_id": str(media_id),
                                "payload_keys": sorted(payload.keys()),
                            },
                        ),
                        context.current_user,
                    )
                mocked_context = [
                    latest for media_id in context.media_ids if (latest := evidence_service.latest_ocr_context(media_id))
                ]
            except MultimodalEvidenceServiceError as exc:
                return AgentToolResult(
                    tool_name=self.tool_name,
                    status="blocked",
                    summary="Mock OCR run could not be created.",
                    blocked_reason="mock_ocr_unavailable",
                    error_message=str(exc),
                    data={"external_api_called": False, "source": "blocked_provider"},
                )
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Created {len(mocked_context)} mocked OCR results through multimodal evidence center.",
                data={
                    "ocr_context": json_safe(mocked_context),
                    "ocr_enabled": settings.OCR_ENABLED,
                    "source": "mocked_ocr",
                    "external_api_called": False,
                    "mocked": True,
                    "not_for_production": True,
                },
            )
        if not settings.OCR_ENABLED:
            gateway_result = self._gateway_dry_run(payload, context)
            return AgentToolResult(
                tool_name=self.tool_name,
                status="blocked",
                summary="OCR is disabled or not configured; provider gateway dry-run did not call external OCR.",
                blocked_reason=gateway_result.get("blocked_reason") or "ocr_disabled",
                data={
                    "ocr_enabled": False,
                    "media_ids": [str(item) for item in context.media_ids],
                    "processing_jobs": json_safe(job_statuses),
                    "external_api_gateway": gateway_result,
                },
            )
        gateway_result = self._gateway_dry_run(payload, context)
        return AgentToolResult(
            tool_name=self.tool_name,
            status="blocked",
            summary="OCR is enabled but no existing OCR text was available for this dry-run tool call.",
            blocked_reason=gateway_result.get("blocked_reason") or "ocr_text_not_available",
            data={
                "ocr_enabled": True,
                "media_ids": [str(item) for item in context.media_ids],
                "processing_jobs": json_safe(job_statuses),
                "external_api_gateway": gateway_result,
            },
        )

    def _gateway_dry_run(self, payload: dict, context: AgentToolExecutionContext) -> dict:
        try:
            result = ExternalApiGateway(context.db).dry_run_for_tool(
                tool_name=self.tool_name,
                capability="ocr",
                current_user=context.current_user,
                agent_code=context.context.get("agent_code"),
                agent_run_id=context.run_id,
                input_summary={
                    "media_count": len(context.media_ids),
                    "media_ids": [str(item) for item in context.media_ids],
                    "payload_keys": sorted(payload.keys()),
                },
            )
            return result.model_dump(mode="json")
        except ExternalApiGatewayError as exc:
            return {
                "status": "blocked",
                "provider_code": None,
                "blocked_reason": "external_api_route_unavailable",
                "message": str(exc),
                "external_api_called": False,
            }


class MediaMimoAnalysisTool(BaseAgentTool):
    tool_name = "media_mimo_analysis"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        evidence_service = MultimodalEvidenceService(context.db)
        analysis_context = []
        job_statuses = []
        for media_id in context.media_ids:
            latest = evidence_service.latest_ai_analysis_context(media_id)
            if latest:
                analysis_context.append(latest)
            else:
                job_status = evidence_service.latest_job_status(media_id, job_type="multimodal_analysis")
                if job_status:
                    job_statuses.append(job_status)
        if analysis_context:
            real_count = sum(
                1
                for item in analysis_context
                if ((item.get("raw_response_json") or {}).get("real_external_api_used") is True)
            )
            mock_count = sum(
                1
                for item in analysis_context
                if ((item.get("raw_response_json") or {}).get("mocked") is True)
            )
            source = "real_analysis" if real_count else "mocked_analysis" if mock_count else "accepted_analysis"
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Found {len(analysis_context)} multimodal analyses from evidence center.",
                data={
                    "analyses": json_safe(analysis_context),
                    "source": source,
                    "provider_mode": "real" if real_count else "mock" if mock_count else "fallback",
                    "external_api_called": bool(real_count),
                    "real_result_count": real_count,
                    "mock_result_count": mock_count,
                    "machine_result_boundary": "Machine analysis is auxiliary evidence and requires field validation.",
                },
            )
        if payload.get("mock_run") and context.media_ids:
            try:
                for media_id in context.media_ids:
                    evidence_service.create_processing_job(
                        media_id,
                        MediaProcessingJobCreate(
                            job_type="multimodal_analysis",
                            provider_code=payload.get("provider_code") or "mimo_2_5",
                            capability=payload.get("capability") or "fault_scene_analysis",
                            analysis_type=payload.get("analysis_type") or "fault_scene",
                            mock_run=True,
                            dry_run=False,
                            agent_run_id=context.run_id,
                            input_summary={
                                "source": "agent_tool",
                                "tool_name": self.tool_name,
                                "media_id": str(media_id),
                                "payload_keys": sorted(payload.keys()),
                                "analysis_scope": "pv_inverter_fault_scene",
                            },
                        ),
                        context.current_user,
                    )
                mocked_context = [
                    latest for media_id in context.media_ids if (latest := evidence_service.latest_ai_analysis_context(media_id))
                ]
            except MultimodalEvidenceServiceError as exc:
                return AgentToolResult(
                    tool_name=self.tool_name,
                    status="blocked",
                    summary="Mock multimodal analysis could not be created.",
                    blocked_reason="mock_multimodal_unavailable",
                    error_message=str(exc),
                    data={"external_api_called": False, "source": "blocked_provider"},
                )
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Created {len(mocked_context)} mocked multimodal analyses through evidence center.",
                data={
                    "analyses": json_safe(mocked_context),
                    "source": "mocked_analysis",
                    "external_api_called": False,
                    "mocked": True,
                    "not_for_production": True,
                    "machine_result_boundary": "Mocked result is local contract evidence only.",
                },
            )
        try:
            gateway_result = ExternalApiGateway(context.db).dry_run_for_tool(
                tool_name=self.tool_name,
                capability="fault_scene_analysis",
                current_user=context.current_user,
                agent_code=context.context.get("agent_code") or "multimodal_evidence_agent",
                agent_run_id=context.run_id,
                input_summary={
                    "media_count": len(context.media_ids),
                    "media_ids": [str(item) for item in context.media_ids],
                    "payload_keys": sorted(payload.keys()),
                    "analysis_scope": "pv_inverter_fault_scene",
                },
            ).model_dump(mode="json")
        except ExternalApiGatewayError as exc:
            gateway_result = {
                "status": "blocked",
                "provider_code": None,
                "blocked_reason": "external_api_route_unavailable",
                "message": str(exc),
                "external_api_called": False,
            }
        return AgentToolResult(
            tool_name=self.tool_name,
            status="blocked",
            summary="mimo-2.5 multimodal analysis is routed through Provider Gateway dry-run and remains blocked.",
            blocked_reason=gateway_result.get("blocked_reason") or "mimo_external_config_missing",
            data={
                "provider": gateway_result.get("provider_code") or "mimo_2_5",
                "external_api_called": False,
                "media_ids": [str(item) for item in context.media_ids],
                "processing_jobs": json_safe(job_statuses),
                "external_api_gateway": gateway_result,
            },
        )
