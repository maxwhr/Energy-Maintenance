from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    AgentArtifactConversion,
    AgentArtifact,
    AgentApproval,
    AgentEventLog,
    AgentRun,
    Device,
    KGCandidate,
    KGExtractionRun,
    KnowledgeContribution,
    MaintenanceTask,
    SOPTemplate,
    User,
)
from app.repositories.agent_repository import AgentRepository
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.schemas.agent import (
    AgentArtifactConversionRequest,
    AgentArtifactConversionResult,
    AgentArtifactConversionStatus,
)


class AgentArtifactConversionServiceError(ValueError):
    pass


class AgentArtifactConversionPermissionError(PermissionError):
    pass


CONVERSION_EVENT_TYPE = "draft_converted_to_formal_object"


ARTIFACT_TARGET_MAP: dict[str, set[str]] = {
    "knowledge_contribution_draft": {"knowledge_contribution"},
    "sop_draft": {"sop_template"},
    "task_draft": {"maintenance_task"},
    "kg_candidate_suggestion": {"kg_candidate"},
}

TARGET_TABLE_MAP: dict[str, str] = {
    "knowledge_contribution": "knowledge_contributions",
    "sop_template": "sop_templates",
    "maintenance_task": "maintenance_tasks",
    "kg_candidate": "kg_extraction_runs",
}

APPROVAL_TYPE_MAP: dict[str, str] = {
    "knowledge_contribution_draft": "knowledge_contribution_draft_review",
    "sop_draft": "sop_draft_review",
    "task_draft": "task_draft_review",
    "kg_candidate_suggestion": "knowledge_contribution_draft_review",
}


class AgentArtifactConversionService:
    def __init__(self, db: Session):
        self.db = db
        self.agent_repository = AgentRepository(db)
        self.kg_repository = KnowledgeGraphRepository(db)

    def get_conversion_status(self, artifact_id: UUID, *, current_user: User) -> AgentArtifactConversionStatus:
        artifact, run = self._load_artifact_and_run(artifact_id)
        self._ensure_can_read(artifact, run, current_user)

        allowed = sorted(ARTIFACT_TARGET_MAP.get(artifact.artifact_type, set()))
        approval = self._find_matching_approval(artifact, status=None)
        conversions = []
        converted_targets = {}
        existing_by_target: dict[str, AgentArtifactConversion] = {}
        for target_type in allowed:
            conversion = self.agent_repository.get_conversion_by_artifact_and_target(artifact.id, target_type)
            if conversion:
                existing_by_target[target_type] = conversion
                result = self._result_from_conversion(conversion, artifact=artifact)
                conversions.append(result)
                if conversion.conversion_status == "succeeded":
                    converted_targets[target_type] = result

        can_convert = current_user.role in {"admin", "expert"} and bool(allowed)
        if approval and approval.status != "approved":
            can_convert = False
        message = None
        blocked_reason = None
        if not allowed:
            message = "Artifact type is not convertible"
            blocked_reason = "unsupported_artifact_type"
        elif not approval:
            message = "Matching approval is required before conversion"
            blocked_reason = "approval_missing"
        elif approval.status != "approved":
            message = "Approval must be approved before conversion"
            blocked_reason = f"approval_{approval.status}"
        elif existing_by_target and all(item.conversion_status in {"succeeded", "converting", "pending"} for item in existing_by_target.values()):
            can_convert = False
            if all(item.conversion_status == "succeeded" for item in existing_by_target.values()):
                message = "All allowed targets have already been converted"
                blocked_reason = "already_converted"
            else:
                message = "Conversion is pending or in progress"
                blocked_reason = "conversion_in_progress"

        return AgentArtifactConversionStatus(
            source_artifact_id=artifact.id,
            source_artifact_type=artifact.artifact_type,
            source_agent_run_id=artifact.run_id,
            allowed_target_types=allowed,
            approval_status=approval.status if approval else None,
            approval_id=approval.id if approval else None,
            conversions=conversions,
            converted_targets=converted_targets,
            can_convert=can_convert,
            already_converted=bool(converted_targets) and len(converted_targets) == len(allowed),
            blocked_reason=blocked_reason,
            message=message,
        )

    def convert_artifact(
        self,
        artifact_id: UUID,
        payload: AgentArtifactConversionRequest,
        *,
        current_user: User,
    ) -> AgentArtifactConversionResult:
        if current_user.role not in {"admin", "expert"}:
            raise AgentArtifactConversionPermissionError("Only expert or admin can convert approved agent artifacts")

        artifact, run = self._load_artifact_and_run(artifact_id)
        artifact = self.agent_repository.lock_artifact_for_conversion(artifact.id) or artifact
        self._validate_target(artifact, payload.target_type)
        approval = self._resolve_approval(artifact, payload.approval_id)
        if approval.status != "approved":
            raise AgentArtifactConversionServiceError("Approval must be approved before conversion")

        existing = self.agent_repository.get_conversion_by_artifact_and_target(artifact.id, payload.target_type)
        if existing:
            return self._result_for_existing_conversion(existing, artifact=artifact)

        content = artifact.content_json or {}
        warnings = self._validate_evidence_boundary(content, payload, current_user)
        conversion_trace_id = f"conv-{uuid4().hex}"
        now = datetime.now(timezone.utc)
        conversion = AgentArtifactConversion(
            source_run_id=run.id,
            source_artifact_id=artifact.id,
            source_approval_id=approval.id,
            target_type=payload.target_type,
            conversion_trace_id=conversion_trace_id,
            requested_by=current_user.id,
            approved_by=approval.reviewed_by,
            request_payload_json=payload.model_dump(mode="json"),
            source_artifact_snapshot_json=self._artifact_snapshot(artifact),
            metadata_json={
                "source_artifact_type": artifact.artifact_type,
                "source_agent_run_id": artifact.run_id,
                "warnings": warnings,
                "approval_status": approval.status,
            },
        )
        created_conversion = self.agent_repository.create_conversion_pending(conversion)
        if created_conversion is not conversion:
            return self._result_for_existing_conversion(created_conversion, artifact=artifact)

        try:
            self.agent_repository.mark_conversion_converting(conversion, started_at=now)
            if payload.target_type == "knowledge_contribution":
                created = self._convert_knowledge_contribution(
                    artifact=artifact,
                    run=run,
                    approval=approval,
                    content=content,
                    current_user=current_user,
                    conversion_trace_id=conversion_trace_id,
                    warnings=warnings,
                    comment=payload.comment,
                )
            elif payload.target_type == "sop_template":
                created = self._convert_sop_template(
                    artifact=artifact,
                    run=run,
                    approval=approval,
                    content=content,
                    current_user=current_user,
                    conversion_trace_id=conversion_trace_id,
                    warnings=warnings,
                    comment=payload.comment,
                )
            elif payload.target_type == "maintenance_task":
                created = self._convert_maintenance_task(
                    artifact=artifact,
                    run=run,
                    approval=approval,
                    content=content,
                    current_user=current_user,
                    conversion_trace_id=conversion_trace_id,
                    warnings=warnings,
                    comment=payload.comment,
                )
            elif payload.target_type == "kg_candidate":
                created = self._convert_kg_candidate(
                    artifact=artifact,
                    run=run,
                    approval=approval,
                    content=content,
                    current_user=current_user,
                    conversion_trace_id=conversion_trace_id,
                    warnings=warnings,
                    comment=payload.comment,
                )
            else:
                raise AgentArtifactConversionServiceError("Unsupported conversion target type")

            completed_at = datetime.now(timezone.utc)
            target_id = UUID(str(created["target_id"]))
            self.agent_repository.mark_conversion_succeeded(
                conversion,
                target_id=target_id,
                target_table=TARGET_TABLE_MAP[payload.target_type],
                target_payload={"target_id": str(target_id), "target_type": payload.target_type},
                result_summary={
                    "created_records": created["created_records"],
                    "message": created["message"],
                    "warnings": warnings,
                },
                completed_at=completed_at,
                converted_by=current_user.id,
            )
            event_payload = {
                "source_artifact_id": str(artifact.id),
                "source_artifact_type": artifact.artifact_type,
                "source_agent_run_id": artifact.run_id,
                "approval_id": str(approval.id),
                "target_type": payload.target_type,
                "target_id": created["target_id"],
                "conversion_trace_id": conversion_trace_id,
                "conversion_id": str(conversion.id),
                "converted_by": str(current_user.id),
                "converted_at": completed_at.isoformat(),
                "warnings": warnings,
                "created_records": created["created_records"],
                "comment": payload.comment,
                "mocked_evidence_used": self._bool_content(content, "mocked_evidence_used"),
                "unreviewed_ai_evidence_used": self._bool_content(content, "unreviewed_ai_evidence_used"),
            }
            self.agent_repository.create_event(
                AgentEventLog(
                    run_id=artifact.run_id,
                    event_type=CONVERSION_EVENT_TYPE,
                    event_message=f"Converted {artifact.artifact_type} to {payload.target_type}",
                    payload_json=event_payload,
                    created_by=current_user.id,
                )
            )
            self.db.commit()
        except Exception as exc:
            safe_error = self._safe_error(exc)
            try:
                self.agent_repository.mark_conversion_failed(
                    conversion,
                    error_message=safe_error,
                    failed_at=datetime.now(timezone.utc),
                )
                self.db.commit()
            except SQLAlchemyError:
                self.db.rollback()
            if isinstance(exc, AgentArtifactConversionServiceError):
                raise
            raise AgentArtifactConversionServiceError(f"Artifact conversion failed: {safe_error}") from exc

        return self._result_from_conversion(conversion, artifact=artifact)

    def list_conversions(
        self,
        *,
        current_user: User,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        conversions, total = self.agent_repository.list_conversions(
            current_user_id=current_user.id,
            include_all=current_user.role in {"admin", "expert"},
            target_type=target_type,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._result_from_conversion(conversion).model_dump(mode="json") for conversion in conversions],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_conversion(self, conversion_trace_id: str, *, current_user: User) -> AgentArtifactConversionResult:
        conversion = self.agent_repository.get_conversion_by_trace_id(conversion_trace_id)
        if not conversion:
            raise AgentArtifactConversionServiceError("Conversion record not found")
        if current_user.role not in {"admin", "expert"} and conversion.requested_by != current_user.id:
            raise AgentArtifactConversionPermissionError("Current user cannot access this conversion record")
        return self._result_from_conversion(conversion)

    def get_conversion_detail(self, conversion_id: UUID, *, current_user: User) -> AgentArtifactConversionResult:
        conversion = self.agent_repository.get_conversion_by_id(conversion_id)
        if not conversion:
            raise AgentArtifactConversionServiceError("Conversion record not found")
        if current_user.role not in {"admin", "expert"} and conversion.requested_by != current_user.id:
            raise AgentArtifactConversionPermissionError("Current user cannot access this conversion record")
        return self._result_from_conversion(conversion)

    def void_conversion(self, conversion_id: UUID, *, current_user: User, reason: str | None = None) -> AgentArtifactConversionResult:
        if current_user.role != "admin":
            raise AgentArtifactConversionPermissionError("Only admin can void conversion records")
        conversion = self.agent_repository.get_conversion_by_id(conversion_id)
        if not conversion:
            raise AgentArtifactConversionServiceError("Conversion record not found")
        raise AgentArtifactConversionServiceError(
            "Conversion void workflow is reserved; no formal business object is deleted or rolled back in this version"
        )

    def list_run_conversions(self, run_id: str, *, current_user: User) -> list[AgentArtifactConversionResult]:
        run = self.agent_repository.get_run(run_id)
        if not run:
            raise AgentArtifactConversionServiceError("Agent run not found")
        if current_user.role not in {"admin", "expert", "viewer"} and run.user_id != current_user.id:
            raise AgentArtifactConversionPermissionError("Current user cannot access this run conversions")
        return [self._result_from_conversion(item) for item in self.agent_repository.get_conversions_for_run(run.id)]

    def list_artifact_conversions(self, artifact_id: UUID, *, current_user: User) -> list[AgentArtifactConversionResult]:
        artifact, run = self._load_artifact_and_run(artifact_id)
        self._ensure_can_read(artifact, run, current_user)
        return [
            self._result_from_conversion(item, artifact=artifact)
            for item in self.agent_repository.get_conversions_for_artifact(artifact_id)
        ]

    def _convert_knowledge_contribution(
        self,
        *,
        artifact: AgentArtifact,
        run: AgentRun,
        approval: AgentApproval,
        content: dict[str, Any],
        current_user: User,
        conversion_trace_id: str,
        warnings: list[str],
        comment: str | None,
    ) -> dict[str, Any]:
        context = run.context_json or {}
        metadata = self._conversion_metadata(artifact, approval, conversion_trace_id, warnings, comment, content)
        contribution = KnowledgeContribution(
            title=self._text(content, "title", default=artifact.title or "Agent knowledge contribution draft"),
            content=self._knowledge_content(content),
            contribution_type=self._text(content, "category", "contribution_type", default="maintenance_experience"),
            manufacturer=self._text(content, "manufacturer", default=context.get("manufacturer")),
            product_series=self._text(content, "product_series", default=context.get("product_series")),
            device_type=self._text(content, "device_type", default=context.get("device_type") or "pv_inverter"),
            device_id=run.device_id,
            source_type="agent_artifact",
            source_trace_id=conversion_trace_id,
            submitted_by=current_user.id,
            review_status="pending_review",
            review_comment="Converted from approved agent draft; knowledge review is still required.",
            metadata_json={
                **metadata,
                "fault_type": self._text(content, "fault_type", default=context.get("fault_type")),
                "alarm_code": self._text(content, "alarm_code", default=context.get("alarm_code")),
                "problem_description": content.get("problem_description"),
                "cause_analysis": content.get("cause_analysis"),
                "troubleshooting_steps": content.get("troubleshooting_steps") or [],
                "solution": content.get("solution"),
                "safety_precautions": content.get("safety_precautions") or [],
                "related_media_ids": content.get("related_media_ids") or run.input_media_ids_json or [],
                "related_agent_run_ids": content.get("related_agent_run_ids") or [artifact.run_id],
                "related_artifact_ids": content.get("related_artifact_ids") or [str(artifact.id)],
            },
        )
        self.db.add(contribution)
        self.db.flush()
        self.db.refresh(contribution)
        return {
            "target_id": str(contribution.id),
            "created_records": {
                "knowledge_contribution_id": str(contribution.id),
                "review_status": contribution.review_status,
                "knowledge_document_created": False,
                "knowledge_chunks_created": False,
            },
            "message": "Knowledge contribution draft converted to pending_review contribution; no document or chunks created.",
        }

    def _convert_sop_template(
        self,
        *,
        artifact: AgentArtifact,
        run: AgentRun,
        approval: AgentApproval,
        content: dict[str, Any],
        current_user: User,
        conversion_trace_id: str,
        warnings: list[str],
        comment: str | None,
    ) -> dict[str, Any]:
        context = run.context_json or {}
        template = SOPTemplate(
            title=self._text(content, "title", default=artifact.title or "Agent SOP draft"),
            manufacturer=self._text(content, "manufacturer", default=context.get("manufacturer")),
            product_series=self._text(content, "product_series", default=context.get("product_series")),
            device_type=self._text(content, "device_type", default=context.get("device_type") or "pv_inverter"),
            fault_type=self._text(content, "fault_type", default=context.get("fault_type") or "unknown"),
            maintenance_level=self._text(content, "maintenance_level", default="level_2"),
            steps=self._list(content.get("steps")),
            safety_requirements=self._list(
                content.get("safety_requirements") or content.get("safety_notes") or content.get("safety_precautions")
            ),
            tools_required=self._list(content.get("tools_required") or content.get("tools")),
            materials_required=self._list(content.get("materials_required") or content.get("materials")),
            compliance_notes=self._text(content, "compliance_notes", default="Converted from approved agent SOP draft."),
            status="draft",
            version=1,
            created_by=current_user.id,
            updated_by=current_user.id,
            metadata_json=self._conversion_metadata(artifact, approval, conversion_trace_id, warnings, comment, content),
        )
        self.db.add(template)
        self.db.flush()
        self.db.refresh(template)
        return {
            "target_id": str(template.id),
            "created_records": {
                "sop_template_id": str(template.id),
                "status": template.status,
                "sop_execution_created": False,
            },
            "message": "SOP draft converted to draft SOP template; no SOP execution created.",
        }

    def _convert_maintenance_task(
        self,
        *,
        artifact: AgentArtifact,
        run: AgentRun,
        approval: AgentApproval,
        content: dict[str, Any],
        current_user: User,
        conversion_trace_id: str,
        warnings: list[str],
        comment: str | None,
    ) -> dict[str, Any]:
        context = run.context_json or {}
        device = self._device_from_run_or_content(run, content, warnings)
        assignee_id = self._valid_assignee_id(content.get("suggested_assignee_id"), warnings)
        task = MaintenanceTask(
            title=self._text(content, "title", default=artifact.title or "Agent maintenance task draft"),
            manufacturer=self._text(content, "manufacturer", default=getattr(device, "manufacturer", None) or context.get("manufacturer")),
            product_series=self._text(content, "product_series", default=getattr(device, "product_series", None) or context.get("product_series")),
            device_type=self._text(content, "device_type", default=getattr(device, "device_type", None) or context.get("device_type") or "pv_inverter"),
            device_id=device.id if device else None,
            device_name=getattr(device, "device_name", None) or self._text(content, "device_name", default=None),
            model=getattr(device, "model", None) or self._text(content, "model", default=None),
            fault_type=self._text(content, "fault_type", default=context.get("fault_type")),
            alarm_code=self._text(content, "alarm_code", default=context.get("alarm_code")),
            fault_description=self._text(content, "description", "fault_description", default=run.input_text),
            priority=self._safe_priority(self._text(content, "priority", default="medium")),
            task_status="pending",
            status="pending",
            assignee_id=assignee_id,
            assignee=None,
            source_type="agent_artifact",
            source_trace_id=conversion_trace_id,
            suggested_steps=self._list(content.get("suggested_steps") or content.get("inspection_steps") or content.get("steps")),
            result_summary="Converted from approved agent task draft; task not started.",
            completion_notes=self._task_conversion_note(artifact, approval, comment),
            created_by=current_user.id,
        )
        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        return {
            "target_id": str(task.id),
            "created_records": {
                "maintenance_task_id": str(task.id),
                "status": task.status,
                "task_status": task.task_status,
                "maintenance_record_created": False,
                "sop_execution_created": False,
                "task_started": False,
                "task_completed": False,
            },
            "message": "Task draft converted to pending maintenance task; no start, completion, or maintenance record created.",
        }

    def _convert_kg_candidate(
        self,
        *,
        artifact: AgentArtifact,
        run: AgentRun,
        approval: AgentApproval,
        content: dict[str, Any],
        current_user: User,
        conversion_trace_id: str,
        warnings: list[str],
        comment: str | None,
    ) -> dict[str, Any]:
        context = run.context_json or {}
        nodes = self._list(content.get("candidate_nodes"))
        edges = self._list(content.get("candidate_edges"))
        if not nodes and not edges:
            raise AgentArtifactConversionServiceError("KG candidate suggestion contains no candidate nodes or edges")

        extraction_run = KGExtractionRun(
            source_type="agent_artifact",
            source_id=artifact.id,
            extractor="agent_artifact_conversion_v1",
            status="completed",
            candidate_count=0,
            approved_count=0,
            rejected_count=0,
            metadata_json=self._conversion_metadata(artifact, approval, conversion_trace_id, warnings, comment, content),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            created_by=current_user.id,
        )
        self.kg_repository.create_run(extraction_run)
        candidates: list[KGCandidate] = []
        for node in nodes:
            node_payload = self._kg_node_payload(node, artifact, context)
            candidates.append(
                KGCandidate(
                    run_id=extraction_run.id,
                    candidate_type="node",
                    payload_json=node_payload,
                    status="pending",
                    confidence=self._confidence(node),
                    evidence_text=node_payload.get("evidence_text"),
                )
            )
        for edge in edges:
            edge_payload = self._kg_edge_payload(edge, artifact, context)
            candidates.append(
                KGCandidate(
                    run_id=extraction_run.id,
                    candidate_type="edge",
                    payload_json=edge_payload,
                    status="pending",
                    confidence=self._confidence(edge),
                    evidence_text=edge_payload.get("evidence_text"),
                )
            )
        self.kg_repository.create_candidates(candidates)
        extraction_run.candidate_count = len(candidates)
        self.kg_repository.update_run(extraction_run)
        return {
            "target_id": str(extraction_run.id),
            "created_records": {
                "kg_extraction_run_id": str(extraction_run.id),
                "kg_candidate_ids": [str(item.id) for item in candidates],
                "kg_candidate_count": len(candidates),
                "kg_nodes_created": False,
                "kg_edges_created": False,
            },
            "message": "KG suggestion converted to pending kg_candidates; no formal KG nodes or edges created.",
        }

    def _load_artifact_and_run(self, artifact_id: UUID) -> tuple[AgentArtifact, AgentRun]:
        artifact = self.agent_repository.get_artifact(artifact_id)
        if not artifact:
            raise AgentArtifactConversionServiceError("Agent artifact not found")
        run = self.agent_repository.get_run(artifact.run_id)
        if not run:
            raise AgentArtifactConversionServiceError("Agent run not found for artifact")
        return artifact, run

    @staticmethod
    def _ensure_can_read(artifact: AgentArtifact, run: AgentRun, current_user: User) -> None:
        if current_user.role in {"admin", "expert", "viewer"} or run.user_id == current_user.id:
            return
        raise AgentArtifactConversionPermissionError("Current user cannot access this artifact conversion status")

    @staticmethod
    def _validate_target(artifact: AgentArtifact, target_type: str) -> None:
        allowed = ARTIFACT_TARGET_MAP.get(artifact.artifact_type, set())
        if target_type not in allowed:
            raise AgentArtifactConversionServiceError(
                f"Artifact type {artifact.artifact_type} cannot be converted to {target_type}"
            )

    def _resolve_approval(self, artifact: AgentArtifact, approval_id: UUID | None) -> AgentApproval:
        expected_type = APPROVAL_TYPE_MAP.get(artifact.artifact_type)
        approval = self.agent_repository.get_approval(approval_id) if approval_id else self._find_matching_approval(artifact, status="approved")
        if not approval:
            raise AgentArtifactConversionServiceError("Approved matching approval is required before conversion")
        if approval.run_id != artifact.run_id:
            raise AgentArtifactConversionServiceError("Approval does not belong to the artifact run")
        if expected_type and approval.approval_type != expected_type:
            raise AgentArtifactConversionServiceError(f"Approval type must be {expected_type}")
        return approval

    def _find_matching_approval(self, artifact: AgentArtifact, *, status: str | None) -> AgentApproval | None:
        expected_type = APPROVAL_TYPE_MAP.get(artifact.artifact_type)
        approvals = self.agent_repository.list_approvals(artifact.run_id)
        matches = [item for item in approvals if item.approval_type == expected_type]
        if status:
            matches = [item for item in matches if item.status == status]
        if not matches:
            return None
        matches.sort(key=lambda item: item.reviewed_at or item.created_at, reverse=True)
        return matches[0]

    @staticmethod
    def _validate_evidence_boundary(
        content: dict[str, Any],
        payload: AgentArtifactConversionRequest,
        current_user: User,
    ) -> list[str]:
        warnings: list[str] = []
        mocked = AgentArtifactConversionService._bool_content(content, "mocked_evidence_used")
        unreviewed = AgentArtifactConversionService._bool_content(content, "unreviewed_ai_evidence_used")
        if mocked:
            warnings.append("Converted draft contains mocked evidence and requires secondary verification.")
        if unreviewed:
            warnings.append("Converted draft contains unreviewed AI evidence and requires admin override.")
        if (mocked or unreviewed) and not (current_user.role == "admin" and payload.override_warnings):
            raise AgentArtifactConversionServiceError(
                "Draft contains mocked or unreviewed evidence; admin override is required for conversion"
            )
        return warnings

    @staticmethod
    def _bool_content(content: dict[str, Any], key: str) -> bool:
        value = content.get(key)
        if isinstance(value, bool):
            return value
        boundary = content.get("evidence_boundary")
        if isinstance(boundary, dict):
            return bool(boundary.get(key))
        return False

    @staticmethod
    def _conversion_metadata(
        artifact: AgentArtifact,
        approval: AgentApproval,
        conversion_trace_id: str,
        warnings: list[str],
        comment: str | None,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source_agent_run_id": artifact.run_id,
            "source_artifact_id": str(artifact.id),
            "source_artifact_type": artifact.artifact_type,
            "approval_id": str(approval.id),
            "conversion_trace_id": conversion_trace_id,
            "conversion_event_type": CONVERSION_EVENT_TYPE,
            "conversion_comment": comment,
            "warnings": warnings,
            "mocked_evidence_used": AgentArtifactConversionService._bool_content(content, "mocked_evidence_used"),
            "unreviewed_ai_evidence_used": AgentArtifactConversionService._bool_content(content, "unreviewed_ai_evidence_used"),
        }

    @staticmethod
    def _knowledge_content(content: dict[str, Any]) -> str:
        sections = [
            ("Problem description", content.get("problem_description")),
            ("Cause analysis", content.get("cause_analysis")),
            ("Troubleshooting steps", content.get("troubleshooting_steps")),
            ("Solution", content.get("solution")),
            ("Safety precautions", content.get("safety_precautions")),
            ("Applicable conditions", content.get("applicable_conditions")),
            ("Not applicable conditions", content.get("not_applicable_conditions")),
        ]
        lines = [f"# {AgentArtifactConversionService._text(content, 'title', default='Agent knowledge contribution')}"]
        for heading, value in sections:
            rendered = AgentArtifactConversionService._render_value(value)
            if rendered:
                lines.append(f"\n## {heading}\n{rendered}")
        return "\n".join(lines).strip()

    @staticmethod
    def _render_value(value: Any) -> str:
        if value in (None, "", []):
            return ""
        if isinstance(value, list):
            return "\n".join(f"- {AgentArtifactConversionService._render_scalar(item)}" for item in value)
        if isinstance(value, dict):
            return "\n".join(f"- {key}: {AgentArtifactConversionService._render_scalar(item)}" for key, item in value.items())
        return str(value).strip()

    @staticmethod
    def _render_scalar(value: Any) -> str:
        if isinstance(value, dict):
            return ", ".join(f"{key}={item}" for key, item in value.items())
        if isinstance(value, list):
            return "; ".join(str(item) for item in value)
        return str(value)

    @staticmethod
    def _text(content: dict[str, Any], *keys: str, default: Any = None) -> str | None:
        for key in keys:
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value not in (None, "", []):
                return str(value)
        if default in (None, "", []):
            return None
        return str(default)

    @staticmethod
    def _list(value: Any) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    @staticmethod
    def _safe_priority(value: str | None) -> str:
        return value if value in {"low", "medium", "high", "urgent", "critical"} else "medium"

    def _device_from_run_or_content(self, run: AgentRun, content: dict[str, Any], warnings: list[str]) -> Device | None:
        device_id = run.device_id or self._uuid_or_none(content.get("device_id"))
        if not device_id:
            return None
        device = self.db.get(Device, device_id)
        if not device:
            warnings.append("Draft referenced a missing device_id; converted task leaves device empty.")
            return None
        return device

    def _valid_assignee_id(self, value: Any, warnings: list[str]) -> UUID | None:
        user_id = self._uuid_or_none(value)
        if not user_id:
            return None
        user = self.db.get(User, user_id)
        if not user or user.role not in {"admin", "expert", "engineer"} or user.status != "active" or not user.is_active:
            warnings.append("Draft suggested an invalid assignee; converted task leaves assignee empty.")
            return None
        return user.id

    @staticmethod
    def _task_conversion_note(artifact: AgentArtifact, approval: AgentApproval, comment: str | None) -> str:
        return (
            "Converted from approved agent task draft; "
            f"source_artifact_id={artifact.id}; approval_id={approval.id}; "
            f"comment={comment or 'none'}"
        )

    @staticmethod
    def _kg_node_payload(node: Any, artifact: AgentArtifact, context: dict[str, Any]) -> dict[str, Any]:
        source = node if isinstance(node, dict) else {"name": str(node)}
        name = str(source.get("canonical_name") or source.get("name") or source.get("display_name") or "PV inverter candidate").strip()
        return {
            "node_type": source.get("node_type") or "maintenance_experience",
            "canonical_name": name,
            "display_name": source.get("display_name") or name,
            "manufacturer": source.get("manufacturer") or context.get("manufacturer"),
            "product_series": source.get("product_series") or context.get("product_series"),
            "device_type": source.get("device_type") or context.get("device_type") or "pv_inverter",
            "properties_json": source,
            "source_type": "agent_artifact",
            "source_id": str(artifact.id),
            "evidence_text": source.get("evidence_text") or source.get("reason") or name,
            "evidence": {
                "source_type": "agent_artifact",
                "source_id": str(artifact.id),
                "evidence_text": source.get("evidence_text") or source.get("reason") or name,
            },
        }

    @staticmethod
    def _kg_edge_payload(edge: Any, artifact: AgentArtifact, context: dict[str, Any]) -> dict[str, Any]:
        source = edge if isinstance(edge, dict) else {"relation": str(edge)}
        source_name = str(source.get("source") or source.get("source_name") or "PV inverter").strip()
        target_name = str(source.get("target") or source.get("target_name") or "maintenance action").strip()
        relation_type = str(source.get("relation_type") or source.get("relation") or "related_to").strip()
        return {
            "source_node": {
                "node_type": source.get("source_node_type") or "device",
                "canonical_name": source_name,
                "display_name": source_name,
                "manufacturer": context.get("manufacturer"),
                "product_series": context.get("product_series"),
                "device_type": context.get("device_type") or "pv_inverter",
            },
            "target_node": {
                "node_type": source.get("target_node_type") or "maintenance_action",
                "canonical_name": target_name,
                "display_name": target_name,
                "manufacturer": context.get("manufacturer"),
                "product_series": context.get("product_series"),
                "device_type": context.get("device_type") or "pv_inverter",
            },
            "relation_type": relation_type,
            "display_relation": source.get("display_relation") or relation_type,
            "properties_json": source,
            "source_type": "agent_artifact",
            "source_id": str(artifact.id),
            "evidence_text": source.get("evidence_text") or f"{source_name} {relation_type} {target_name}",
            "evidence": {
                "source_type": "agent_artifact",
                "source_id": str(artifact.id),
                "evidence_text": source.get("evidence_text") or f"{source_name} {relation_type} {target_name}",
            },
        }

    @staticmethod
    def _confidence(value: Any) -> float:
        if isinstance(value, dict):
            try:
                return max(0.0, min(1.0, float(value.get("confidence") or 0.6)))
            except (TypeError, ValueError):
                return 0.6
        return 0.6

    @staticmethod
    def _uuid_or_none(value: Any) -> UUID | None:
        if not value:
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    def _result_for_existing_conversion(
        self,
        conversion: AgentArtifactConversion,
        *,
        artifact: AgentArtifact | None = None,
    ) -> AgentArtifactConversionResult:
        result = self._result_from_conversion(conversion, artifact=artifact)
        if conversion.conversion_status == "succeeded":
            result.already_converted = True
            result.can_convert = False
            result.blocked_reason = "already_converted"
            result.message = "Artifact has already been converted; no duplicate formal object was created."
            result.status = "already_converted"
        elif conversion.conversion_status in {"pending", "converting"}:
            result.can_convert = False
            result.blocked_reason = "conversion_in_progress"
            result.message = "Artifact conversion is already pending or in progress; no duplicate formal object was created."
            result.status = "conversion_in_progress"
        elif conversion.conversion_status == "failed":
            result.can_convert = False
            result.blocked_reason = "previous_conversion_failed"
            result.message = "Previous conversion failed and remains recorded; administrator review is required before retry."
        elif conversion.conversion_status == "voided":
            result.can_convert = False
            result.blocked_reason = "conversion_voided"
            result.message = "Conversion record is voided; rollback/retry workflow is reserved for a later task."
        return result

    @staticmethod
    def _artifact_snapshot(artifact: AgentArtifact) -> dict[str, Any]:
        return {
            "id": str(artifact.id),
            "run_id": artifact.run_id,
            "artifact_type": artifact.artifact_type,
            "title": artifact.title,
            "content_text": artifact.content_text,
            "content_json": artifact.content_json or {},
            "source_type": artifact.source_type,
            "source_id": artifact.source_id,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        text = str(exc) or exc.__class__.__name__
        for marker in ("Authorization", "api_key", "token", "password", "secret"):
            if marker.lower() in text.lower():
                return "Conversion failed with sanitized sensitive error"
        return text[:500]

    @staticmethod
    def _result_from_conversion(
        conversion: AgentArtifactConversion,
        *,
        artifact: AgentArtifact | None = None,
    ) -> AgentArtifactConversionResult:
        metadata = conversion.metadata_json or {}
        summary = conversion.result_summary_json or {}
        created_records = summary.get("created_records") if isinstance(summary, dict) else None
        warnings = summary.get("warnings") if isinstance(summary, dict) else None
        source_artifact_type = (
            artifact.artifact_type
            if artifact
            else str(metadata.get("source_artifact_type") or "")
        )
        source_agent_run_id = (
            artifact.run_id
            if artifact
            else str(metadata.get("source_agent_run_id") or "")
        )
        converted_at = conversion.completed_at or conversion.failed_at or conversion.voided_at or conversion.created_at
        return AgentArtifactConversionResult(
            id=conversion.id,
            conversion_trace_id=conversion.conversion_trace_id,
            source_artifact_id=conversion.source_artifact_id,
            source_artifact_type=source_artifact_type,
            source_agent_run_id=source_agent_run_id,
            approval_id=conversion.source_approval_id,
            target_type=conversion.target_type,
            target_id=str(conversion.target_id) if conversion.target_id else None,
            target_table=conversion.target_table,
            status=conversion.conversion_status,
            conversion_status=conversion.conversion_status,
            warnings=list(warnings or metadata.get("warnings") or []),
            created_records=dict(created_records or {}),
            message=str(summary.get("message") or conversion.error_message or f"Conversion {conversion.conversion_status}"),
            result_summary=dict(summary or {}),
            metadata=dict(metadata or {}),
            already_converted=False,
            can_convert=False,
            blocked_reason=None,
            converted_by=conversion.converted_by,
            requested_by=conversion.requested_by,
            approved_by=conversion.approved_by,
            voided_by=conversion.voided_by,
            created_at=conversion.created_at,
            started_at=conversion.started_at,
            completed_at=conversion.completed_at,
            failed_at=conversion.failed_at,
            voided_at=conversion.voided_at,
            converted_at=converted_at,
            error_message=conversion.error_message,
        )

    @staticmethod
    def _result_from_event(event: AgentEventLog) -> AgentArtifactConversionResult:
        payload = event.payload_json or {}
        converted_at = payload.get("converted_at")
        try:
            converted_dt = datetime.fromisoformat(str(converted_at))
        except (TypeError, ValueError):
            converted_dt = event.created_at
        return AgentArtifactConversionResult(
            conversion_trace_id=str(payload.get("conversion_trace_id") or ""),
            source_artifact_id=UUID(str(payload.get("source_artifact_id"))),
            source_artifact_type=str(payload.get("source_artifact_type") or ""),
            source_agent_run_id=str(payload.get("source_agent_run_id") or event.run_id or ""),
            approval_id=AgentArtifactConversionService._uuid_or_none(payload.get("approval_id")),
            target_type=payload.get("target_type"),
            target_id=str(payload.get("target_id") or ""),
            status="succeeded",
            warnings=payload.get("warnings") or [],
            created_records=payload.get("created_records") or {},
            message=str(event.event_message or "Artifact converted"),
            converted_by=AgentArtifactConversionService._uuid_or_none(payload.get("converted_by") or event.created_by),
            converted_at=converted_dt,
        )

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise AgentArtifactConversionServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise AgentArtifactConversionServiceError("page_size must be between 1 and 100")
