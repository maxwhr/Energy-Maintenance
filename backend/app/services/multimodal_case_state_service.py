from __future__ import annotations

import hashlib
import json
import re
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import MultimodalEvidenceItem, MultimodalMaintenanceCase, OperationLog, User
from app.repositories.multimodal_case_repository import MultimodalCaseRepository
from app.schemas.multimodal_case import (
    EvidenceDecisionRequest,
    MultimodalCaseCreate,
    MultimodalCasePage,
    MultimodalCaseRead,
    MultimodalEvidenceCreate,
    MultimodalEvidenceRead,
    MultimodalCaseClarify,
)
from app.services.query_understanding_service import QueryUnderstandingService


class MultimodalCaseError(ValueError):
    pass


class MultimodalCasePermissionError(PermissionError):
    pass


class MultimodalCaseStateService:
    TRANSITIONS = {
        "DRAFT": {"MEDIA_UPLOADED", "ANALYZING", "NEEDS_CLARIFICATION", "INSUFFICIENT_EVIDENCE", "FAILED", "ARCHIVED"},
        "MEDIA_UPLOADED": {"ANALYZING", "NEEDS_CLARIFICATION", "EVIDENCE_READY", "FAILED", "ARCHIVED"},
        "ANALYZING": {"EVIDENCE_READY", "NEEDS_CLARIFICATION", "DIAGNOSIS_READY", "MULTIPLE_POSSIBILITIES", "INSUFFICIENT_EVIDENCE", "FAILED", "ARCHIVED"},
        "NEEDS_CLARIFICATION": {"ANALYZING", "EVIDENCE_READY", "INSUFFICIENT_EVIDENCE", "ARCHIVED"},
        "EVIDENCE_READY": {"ANALYZING", "DIAGNOSIS_READY", "MULTIPLE_POSSIBILITIES", "NEEDS_CLARIFICATION", "INSUFFICIENT_EVIDENCE", "SOP_DRAFT_READY", "ARCHIVED"},
        "DIAGNOSIS_READY": {"MULTIPLE_POSSIBILITIES", "SOP_DRAFT_READY", "TASK_DRAFT_READY", "ARCHIVED"},
        "MULTIPLE_POSSIBILITIES": {"NEEDS_CLARIFICATION", "DIAGNOSIS_READY", "SOP_DRAFT_READY", "ARCHIVED"},
        "INSUFFICIENT_EVIDENCE": {"NEEDS_CLARIFICATION", "ANALYZING", "ARCHIVED"},
        "SOP_DRAFT_READY": {"DIAGNOSIS_READY", "TASK_DRAFT_READY", "ARCHIVED"},
        "TASK_DRAFT_READY": {"ARCHIVED"},
        "FAILED": {"DRAFT", "MEDIA_UPLOADED", "ANALYZING", "ARCHIVED"},
        "ARCHIVED": set(),
    }

    def __init__(self, db: Session):
        self.db = db
        self.repository = MultimodalCaseRepository(db)

    def create(self, payload: MultimodalCaseCreate, user: User) -> MultimodalCaseRead:
        if payload.idempotency_key:
            existing = self.repository.get_by_idempotency_key(payload.idempotency_key)
            if existing:
                self._require_access(existing, user)
                return self.to_read(existing)
        case_id = f"mmc_{uuid4().hex}"
        item = MultimodalMaintenanceCase(
            case_id=case_id,
            idempotency_key=payload.idempotency_key,
            title=payload.title.strip(),
            status="DRAFT",
            user_query=(payload.user_query or "").strip() or None,
            normalized_query=self._normalize(payload.user_query),
            conversation_id=payload.conversation_id,
            device_id=payload.device_id,
            device_model=self._clean(payload.device_model),
            product_family=self._clean(payload.product_family),
            equipment_category=self._clean(payload.equipment_category),
            reported_symptoms=self._unique(payload.reported_symptoms),
            occurrence_conditions=self._unique(payload.occurrence_conditions),
            created_by=user.id,
            metadata_json={
                "formal_task_created": False,
                "formal_sop_approved": False,
                "dedicated_rerank_status": "DEFERRED_QWEN3_RERANK_CONFIG",
            },
        )
        try:
            saved = self.repository.create_case(item)
            self._audit(saved, user, "case_created", None, "DRAFT", {"idempotent": bool(payload.idempotency_key)})
            if saved.user_query:
                analysis = QueryUnderstandingService().understand(saved.user_query)
                explicit_alarm_context = bool(re.search(r"(?:告警|故障)(?:代码|码)?\s*[:：#]?\s*[A-Z0-9_-]{3,12}", saved.user_query, re.I))
                source_hash = hashlib.sha256(saved.user_query.encode("utf-8")).hexdigest()
                self.add_evidence(saved, MultimodalEvidenceCreate(
                    modality="USER_TEXT",
                    evidence_type="DEVICE_MODEL" if analysis.device_models else ("ALARM_CODE" if explicit_alarm_context and analysis.fault_codes else "GENERAL_OBSERVATION"),
                    source_type="USER_INPUT",
                    source_hash=source_hash,
                    observed_text=saved.user_query,
                    normalized_text=saved.normalized_query,
                    device_model_candidates=analysis.device_models,
                    alarm_code_candidates=analysis.fault_codes if explicit_alarm_context else [],
                    component_candidates=analysis.component_terms,
                    symptom_candidates=analysis.symptom_terms,
                    confidence=1.0,
                    observation_status="USER_CONFIRMED",
                ), user, allow_user_confirmed=True)
            self.db.commit()
            return self.to_read(saved)
        except (IntegrityError, SQLAlchemyError) as exc:
            self.db.rollback()
            if payload.idempotency_key:
                existing = self.repository.get_by_idempotency_key(payload.idempotency_key)
                if existing:
                    return self.to_read(existing)
            raise MultimodalCaseError(f"case write failed: {exc.__class__.__name__}") from exc

    def get(self, case_id: str, user: User) -> MultimodalMaintenanceCase:
        item = self.repository.get_case(case_id)
        if not item:
            raise MultimodalCaseError("Multimodal maintenance case not found")
        self._require_access(item, user)
        return item

    def list(self, user: User, *, status: str | None, page: int, page_size: int) -> MultimodalCasePage:
        owner = None if user.role in {"admin", "expert"} else user.id
        items, total = self.repository.list_cases(created_by=owner, status=status, page=page, page_size=page_size)
        return MultimodalCasePage(items=[self.to_read(item) for item in items], total=total, page=page, page_size=page_size)

    def transition(self, item: MultimodalMaintenanceCase, target: str, user: User, *, reason: str, detail: dict | None = None) -> MultimodalMaintenanceCase:
        if target == item.status:
            return item
        if target not in self.TRANSITIONS.get(item.status, set()):
            raise MultimodalCaseError(f"Invalid case status transition: {item.status} -> {target}")
        before = item.status
        item.status = target
        if target != "FAILED":
            item.last_error_code = None
            item.last_error_message = None
        saved = self.repository.save_case(item)
        self._audit(saved, user, "status_transition", before, target, {"reason": reason, **(detail or {})})
        return saved

    def add_evidence(
        self,
        case: MultimodalMaintenanceCase,
        payload: MultimodalEvidenceCreate,
        user: User,
        *,
        allow_user_confirmed: bool = False,
    ) -> MultimodalEvidenceItem:
        existing = self.repository.get_evidence_by_identity(case.case_id, payload.source_hash, payload.evidence_type)
        if existing:
            return existing
        if payload.observation_status == "USER_CONFIRMED" and not allow_user_confirmed:
            raise MultimodalCaseError("evidence must be confirmed through the audited confirm endpoint")
        item = MultimodalEvidenceItem(
            evidence_id=f"mme_{uuid4().hex}",
            case_id=case.case_id,
            created_by=user.id,
            user_confirmed=payload.observation_status == "USER_CONFIRMED",
            contradicted=payload.observation_status == "CONTRADICTED",
            **payload.model_dump(),
        )
        saved = self.repository.create_evidence(item)
        self._audit(case, user, "evidence_added", case.status, case.status, {
            "evidence_id": saved.evidence_id,
            "modality": saved.modality,
            "evidence_type": saved.evidence_type,
            "source_hash": saved.source_hash,
            "observation_status": saved.observation_status,
        })
        return saved

    def decide_evidence(
        self,
        case: MultimodalMaintenanceCase,
        evidence_id: str,
        payload: EvidenceDecisionRequest,
        user: User,
        *,
        accept: bool,
    ) -> MultimodalEvidenceRead:
        if user.role not in {"admin", "expert", "engineer"}:
            raise MultimodalCasePermissionError("viewer cannot modify multimodal evidence")
        evidence = self.repository.get_evidence(case.case_id, evidence_id)
        if not evidence:
            raise MultimodalCaseError("Evidence item not found")
        before = evidence.observation_status
        evidence.observation_status = "USER_CONFIRMED" if accept else "REJECTED"
        evidence.user_confirmed = accept
        evidence.contradicted = not accept
        evidence.contradiction_reason = None if accept else (payload.reason or "rejected_by_user")
        if accept and payload.confirmed_value:
            evidence.normalized_text = payload.confirmed_value.strip()
        saved = self.repository.save_evidence(evidence)
        facts = dict(case.user_confirmed_facts or {})
        if accept:
            facts[saved.evidence_id] = {
                "evidence_type": saved.evidence_type,
                "value": saved.normalized_text or saved.observed_text,
                "confirmed_by": str(user.id),
            }
        else:
            facts.pop(saved.evidence_id, None)
        case.user_confirmed_facts = facts
        self.repository.save_case(case)
        self._audit(case, user, "evidence_confirmed" if accept else "evidence_rejected", before, saved.observation_status, {
            "evidence_id": saved.evidence_id,
            "reason": payload.reason,
        })
        self.db.commit()
        return MultimodalEvidenceRead.model_validate(saved)

    def clarify(
        self,
        case: MultimodalMaintenanceCase,
        payload: MultimodalCaseClarify,
        user: User,
    ) -> MultimodalCaseRead:
        if user.role not in {"admin", "expert", "engineer"}:
            raise MultimodalCasePermissionError("viewer cannot clarify a multimodal case")
        if case.status not in {"NEEDS_CLARIFICATION", "INSUFFICIENT_EVIDENCE", "DRAFT", "EVIDENCE_READY"}:
            raise MultimodalCaseError(f"case cannot be clarified from status {case.status}")
        facts = dict(case.user_confirmed_facts or {})
        answers = {str(key).strip(): str(value).strip() for key, value in payload.answers.items() if str(value).strip()}
        explicit = {**answers, **payload.confirmed_facts}
        for key, value in explicit.items():
            normalized_value = str(value).strip()
            if not normalized_value:
                continue
            evidence_type = {
                "device_model": "DEVICE_MODEL",
                "alarm_code": "ALARM_CODE",
                "indicator_state": "INDICATOR_LIGHT",
                "component": "COMPONENT",
            }.get(key, "GENERAL_OBSERVATION")
            source_hash = hashlib.sha256(
                json.dumps([case.case_id, key, normalized_value], ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            evidence = self.add_evidence(case, MultimodalEvidenceCreate(
                modality="USER_TEXT",
                evidence_type=evidence_type,
                source_type="USER_INPUT",
                source_hash=source_hash,
                observed_text=normalized_value,
                normalized_text=normalized_value,
                device_model_candidates=[normalized_value] if evidence_type == "DEVICE_MODEL" else [],
                alarm_code_candidates=[normalized_value] if evidence_type == "ALARM_CODE" else [],
                component_candidates=[normalized_value] if evidence_type == "COMPONENT" else [],
                indicator_state_candidates=[normalized_value] if evidence_type == "INDICATOR_LIGHT" else [],
                confidence=1.0,
                observation_status="USER_CONFIRMED",
                metadata_json={"clarification_key": key},
            ), user, allow_user_confirmed=True)
            facts[evidence.evidence_id] = {
                "evidence_type": evidence_type,
                "value": normalized_value,
                "confirmed_by": str(user.id),
                "clarification_key": key,
            }
        case.user_confirmed_facts = facts
        answered_keys = set(answers)
        case.missing_information = [item for item in (case.missing_information or []) if item not in answered_keys]
        case.clarifying_questions = []
        self.repository.save_case(case)
        self._audit(case, user, "case_clarified", case.status, case.status, {
            "answered_fields": sorted(explicit),
            "confirmed_fact_count": len(facts),
        })
        if case.status != "EVIDENCE_READY":
            self.transition(case, "ANALYZING", user, reason="clarification_received")
        self.db.commit()
        return self.to_read(case)

    def audit(
        self,
        case: MultimodalMaintenanceCase,
        user: User,
        action: str,
        *,
        before: str | None = None,
        after: str | None = None,
        detail: dict | None = None,
    ) -> None:
        self._audit(case, user, action, before or case.status, after or case.status, detail or {})

    def to_read(self, item: MultimodalMaintenanceCase) -> MultimodalCaseRead:
        data = MultimodalCaseRead.model_validate(item).model_dump()
        data.update(self.repository.counts(item.case_id))
        return MultimodalCaseRead(**data)

    def _audit(self, case: MultimodalMaintenanceCase, user: User, action: str, before: str | None, after: str | None, detail: dict) -> None:
        trace_seed = json.dumps([case.case_id, action, before, after, detail], ensure_ascii=False, sort_keys=True, default=str)
        self.repository.add_audit(OperationLog(
            module="multimodal_case",
            action=action,
            target_type="multimodal_case",
            target_id=case.case_id,
            operator=user.username,
            trace_id=f"mmc-{hashlib.sha256(trace_seed.encode('utf-8')).hexdigest()[:28]}",
            detail={
                "before_status": before,
                "after_status": after,
                "operator_id": str(user.id),
                "automatic_approval": False,
                "formal_task_created": False,
                **detail,
            },
        ))

    @staticmethod
    def _require_access(item: MultimodalMaintenanceCase, user: User) -> None:
        if user.role not in {"admin", "expert"} and item.created_by != user.id:
            raise MultimodalCasePermissionError("Permission denied for this multimodal case")

    @staticmethod
    def _normalize(value: str | None) -> str | None:
        return " ".join((value or "").split()).strip() or None

    @staticmethod
    def _clean(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))
