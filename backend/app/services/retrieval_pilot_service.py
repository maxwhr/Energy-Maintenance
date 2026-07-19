from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    KnowledgeChunk,
    KnowledgeChunkVectorIndex,
    KnowledgeDocument,
    RetrievalDatasetFreeze,
    RetrievalEvaluationCase,
    RetrievalOfficialRunLock,
    User,
    VectorIndexRun,
)
from app.repositories.retrieval_pilot_repository import RetrievalPilotRepository
from app.schemas.retrieval_pilot import BenchmarkReviewRequest, PilotRouteDecision, PilotSessionCreate


class RetrievalPilotServiceError(ValueError):
    pass


class RetrievalPilotService:
    RUN_PURPOSE = "task25b_r2_official_pilot_test"

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repository = RetrievalPilotRepository(db)

    def status(self) -> dict:
        cases = self.repository.all_cases()
        counts = Counter(case.review_status for case in cases)
        freezes = self.repository.list_freezes()
        sessions = self.repository.active_sessions()
        formal_filter = (
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeChunk.status == "active",
        )
        formal_chunks = int(
            self.db.scalar(
                select(func.count())
                .select_from(KnowledgeChunk)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(*formal_filter)
            )
            or 0
        )
        use_partition = bool(getattr(self.settings, "DASHVECTOR_USE_PARTITIONS", False))
        pilot_collection = (
            self.settings.DASHVECTOR_PHYSICAL_COLLECTION
            if use_partition
            else self.settings.DASHVECTOR_PILOT_COLLECTION
        )
        pilot_partition = getattr(self.settings, "DASHVECTOR_PILOT_PARTITION", "") if use_partition else "default"
        pilot_index_filters = [
            KnowledgeChunkVectorIndex.collection_name == pilot_collection,
            KnowledgeChunkVectorIndex.index_status == "active",
        ]
        if use_partition:
            pilot_index_filters.append(KnowledgeChunkVectorIndex.namespace == pilot_partition)
        pilot_records = int(
            self.db.scalar(
                select(func.count())
                .select_from(KnowledgeChunkVectorIndex)
                .where(*pilot_index_filters)
            )
            or 0
        )
        expert = counts.get("expert_verified", 0)
        second = sum(bool((case.metadata_json or {}).get("second_reviews")) for case in cases)
        pilot_gate_met = formal_chunks >= 300 and expert >= 100 and second >= 20
        return {
            "version": "task25b-r2",
            "notice": (
                "Pilot 门禁已满足，可进入显式恢复检查。"
                if pilot_gate_met
                else "Pilot 门禁未满足：索引保持 blocked，正式默认检索不受影响。"
            ),
            "pilot_enabled": self.settings.TASK25B_R2_PILOT_ENABLED,
            "base_collection": self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "pilot_collection": pilot_collection,
            "pilot_partition": pilot_partition,
            "collection_isolation_mode": "partition" if use_partition else "collection",
            "collection_isolation_required": True,
            "collection_isolated_by_name": not use_partition and pilot_collection != self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "partition_isolated": use_partition and bool(pilot_partition),
            "default_strategy": self.settings.RETRIEVAL_DEFAULT_MODE,
            "pilot_strategy": self.settings.RETRIEVAL_PILOT_MODE,
            "full_reindex_allowed": self.settings.TASK25B_ALLOW_FULL_REINDEX,
            "formal_approved_active_chunks_including_preexisting_controlled": formal_chunks,
            "pilot_index_records": pilot_records,
            "pilot_index_allowed": pilot_gate_met,
            "benchmark": {
                "total": len(cases),
                "review_status": dict(counts),
                "expert_verified": expert,
                "second_reviewed": second,
                "expert_gate_met": expert >= 100 and second >= 20,
                "vector_heavy": sum(bool((case.metadata_json or {}).get("vector_heavy")) for case in cases),
                "no_answer": sum(case.category == "no_answer" for case in cases),
            },
            "freeze_status": [self._freeze_dict(item) for item in freezes],
            "active_pilot_sessions": [str(item.id) for item in sessions],
            "official_run_status": "blocked_expert_review" if expert < 100 else "ready_for_freeze",
        }

    def u3_status(self) -> dict:
        official_filter = (
            KnowledgeDocument.manufacturer == "huawei",
            KnowledgeDocument.source_type.in_(["vendor_official", "vendor_official_html"]),
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
        )
        documents = list(self.db.scalars(select(KnowledgeDocument).where(*official_filter)))
        pending = [item for item in documents if item.review_status == "pending_review"]
        approved = [
            item for item in documents
            if item.review_status == "approved" and bool((item.metadata_json or {}).get("approved_for_pilot"))
        ]
        cases = self.repository.all_cases()
        expert = sum(item.review_status == "expert_verified" for item in cases)
        second = sum(bool((item.metadata_json or {}).get("second_reviews")) for item in cases)
        active_approved_chunks = sum(item.chunk_count for item in approved)
        corpus_gate_status = "CORPUS_READY" if len(approved) >= 15 and active_approved_chunks >= 300 else "CORPUS_BLOCKED"
        return {
            "version": "task25b-r2-u3",
            "status": "AWAITING_HUMAN_DOCUMENT_APPROVAL" if pending else (
                "AWAITING_HUMAN_BENCHMARK_REVIEW" if expert < 100 or second < 20 else "READY_FOR_EXPLICIT_RESUME_CHECK"
            ),
            "pending_official_documents": len(pending),
            "approved_official_documents": len(approved),
            "projected_chunks_after_approval": sum(item.chunk_count for item in documents if not (item.metadata_json or {}).get("marketing_only")),
            "active_approved_chunks": sum(item.chunk_count for item in approved),
            "required_active_chunks": 300,
            "corpus_gate_status": corpus_gate_status,
            "pilot_index_allowed": corpus_gate_status == "CORPUS_READY" and expert >= 100 and second >= 20,
            "expert_verified": expert, "second_reviewed": second,
            "document_review_url": "/review", "benchmark_review_url": "/system/retrieval-quality",
            "collection": self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "pilot_partition": self.settings.DASHVECTOR_PILOT_PARTITION,
            "pilot_index_executed": False,
            "full_reindex_allowed": self.settings.TASK25B_ALLOW_FULL_REINDEX,
            "automatic_approval": False, "automatic_expert_verification": False,
        }

    def pilot_index_preflight(self, *, allow_real_api: bool, pilot_only: bool, approved_only: bool) -> dict:
        failures = []
        use_partition = bool(getattr(self.settings, "DASHVECTOR_USE_PARTITIONS", False))
        pilot_collection = (
            self.settings.DASHVECTOR_PHYSICAL_COLLECTION
            if use_partition
            else self.settings.DASHVECTOR_PILOT_COLLECTION
        )
        pilot_partition = getattr(self.settings, "DASHVECTOR_PILOT_PARTITION", "") if use_partition else "default"
        if not self.settings.TASK25B_R2_PILOT_ENABLED or not self.settings.TASK25B_R2_ALLOW_PILOT_INDEX:
            failures.append("pilot_index_gate_disabled")
        if not allow_real_api or not self.settings.TASK25B_ALLOW_REAL_API:
            failures.append("real_api_not_explicitly_allowed")
        if not pilot_only or not approved_only:
            failures.append("pilot_only_and_approved_only_are_required")
        if use_partition and not pilot_partition:
            failures.append("pilot_partition_not_configured")
        if not use_partition and pilot_collection == self.settings.DASHVECTOR_PHYSICAL_COLLECTION:
            failures.append("pilot_collection_not_isolated")
        return {
            "accepted": not failures,
            "status": "READY_FOR_SCRIPTED_INDEX" if not failures else "BLOCKED_CONFIG",
            "failures": failures,
            "pilot_collection": pilot_collection,
            "pilot_partition": pilot_partition,
            "isolation_mode": "partition" if use_partition else "collection",
            "base_collection": self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "execution_contract": "backend/scripts/run_task25b_r2_u2_pilot_index.py" if use_partition else "backend/scripts/run_task25b_r2_pilot_index.py",
            "full_reindex_executed": False,
        }

    def list_index_runs(self, *, page: int, page_size: int) -> dict:
        filters = [VectorIndexRun.run_type.in_(["task25b_r2_pilot_index", "task25b_r2_pilot_session"])]
        total = int(self.db.scalar(select(func.count()).select_from(VectorIndexRun).where(*filters)) or 0)
        items = list(
            self.db.scalars(
                select(VectorIndexRun).where(*filters).order_by(VectorIndexRun.created_at.desc())
                .offset((page - 1) * page_size).limit(page_size)
            )
        )
        return {
            "items": [
                {
                    "id": str(item.id), "run_type": item.run_type, "status": item.status,
                    "collection_name": item.collection_name, "total_count": item.total_count,
                    "succeeded_count": item.succeeded_count, "failed_count": item.failed_count,
                    "skipped_count": item.skipped_count, "created_at": item.created_at,
                }
                for item in items
            ],
            "total": total, "page": page, "page_size": page_size,
        }

    def reconcile_summary(self, *, allow_real_api: bool) -> dict:
        use_partition = bool(getattr(self.settings, "DASHVECTOR_USE_PARTITIONS", False))
        pilot_collection = (
            self.settings.DASHVECTOR_PHYSICAL_COLLECTION
            if use_partition
            else self.settings.DASHVECTOR_PILOT_COLLECTION
        )
        pilot_partition = getattr(self.settings, "DASHVECTOR_PILOT_PARTITION", "") if use_partition else "default"
        filters = [
            KnowledgeChunkVectorIndex.collection_name == pilot_collection,
            KnowledgeChunkVectorIndex.index_status == "active",
        ]
        if use_partition:
            filters.append(KnowledgeChunkVectorIndex.namespace == pilot_partition)
        records = int(
            self.db.scalar(
                select(func.count()).select_from(KnowledgeChunkVectorIndex).where(*filters)
            ) or 0
        )
        return {
            "status": "READY_FOR_EXTERNAL_RECONCILIATION" if allow_real_api and records else "BLOCKED_NO_PILOT_INDEX",
            "postgresql_records": records,
            "dashvector_vectors": None,
            "external_api_called": False,
            "pilot_collection": pilot_collection,
            "pilot_partition": pilot_partition,
            "execution_contract": "backend/scripts/check_task25b_r2_u2_pilot_reconciliation.py" if use_partition else "backend/scripts/check_task25b_r2_pilot_reconciliation.py",
            "missing": None, "orphan": None, "stale": None, "duplicate": None,
        }

    def list_cases(self, **filters) -> dict:
        items, total = self.repository.list_cases(**filters)
        return {
            "items": [self._case_dict(item) for item in items],
            "total": total,
            "page": filters["page"],
            "page_size": filters["page_size"],
        }

    def review_case(self, case_id: UUID, payload: BenchmarkReviewRequest, user: User, *, expert: bool) -> dict:
        case = self.repository.get_case(case_id)
        if not case:
            raise RetrievalPilotServiceError("Benchmark case not found")
        self._ensure_not_frozen(case_id)
        metadata = dict(case.metadata_json or {})
        history = list(metadata.get("review_history") or [])
        before = {
            "review_status": case.review_status,
            "query_sha256": hashlib.sha256(case.query_text.encode("utf-8")).hexdigest(),
            "expected_document_ids": [str(item) for item in case.expected_document_ids or []],
            "expected_chunk_ids": [str(item) for item in case.expected_chunk_ids or []],
        }
        trace_id = f"r2-review-{uuid4().hex}"
        if expert:
            if user.role not in self.allowed_review_roles(expert=True):
                raise RetrievalPilotServiceError("Only expert/admin can submit expert review")
            primary = metadata.get("primary_reviewer_id")
            if payload.second_review:
                if not primary:
                    raise RetrievalPilotServiceError("Primary expert review is required before second review")
                if str(primary) == str(user.id):
                    raise RetrievalPilotServiceError("Second reviewer must differ from primary reviewer")
                second_reviews = list(metadata.get("second_reviews") or [])
                if any(str(item.get("reviewer_id")) == str(user.id) for item in second_reviews):
                    raise RetrievalPilotServiceError("This reviewer already submitted the second review")
                second_reviews.append({
                    "reviewer_id": str(user.id), "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "decision": payload.decision, "notes": payload.notes,
                })
                metadata["second_reviews"] = second_reviews
            else:
                metadata["primary_reviewer_id"] = str(user.id)
                metadata["primary_reviewed_at"] = datetime.now(timezone.utc).isoformat()
                case.review_status = {
                    "approve": "expert_verified",
                    "reject": "expert_rejected",
                    "needs_revision": "needs_revision",
                }[payload.decision]
                case.reviewed_by = user.id
        else:
            if user.role not in self.allowed_review_roles(expert=False):
                raise RetrievalPilotServiceError("Engineer role or above is required")
            case.review_status = "engineering_verified" if payload.decision == "approve" else (
                "needs_revision" if payload.decision == "needs_revision" else "rejected"
            )
            case.reviewed_by = user.id
        if payload.suggested_query:
            case.query_text = payload.suggested_query
        if payload.suggested_expected_ids:
            case.expected_chunk_ids = [str(item) for item in payload.suggested_expected_ids]
        after = {
            "review_status": case.review_status,
            "query_sha256": hashlib.sha256(case.query_text.encode("utf-8")).hexdigest(),
            "expected_document_ids": [str(item) for item in case.expected_document_ids or []],
            "expected_chunk_ids": [str(item) for item in case.expected_chunk_ids or []],
        }
        history.append({
            "reviewer_id": str(user.id), "reviewer_role": user.role,
            "reviewed_at": datetime.now(timezone.utc).isoformat(), "expert_review": expert,
            "second_review": payload.second_review, "decision": payload.decision,
            "validity": {
                "query": payload.query_valid, "expected_reference": payload.expected_reference_valid,
                "difficulty": payload.difficulty_valid, "category": payload.category_valid,
            },
            "notes": payload.notes, "before": before, "after": after, "trace_id": trace_id,
        })
        metadata["review_history"] = history
        metadata["second_review_required"] = True
        case.metadata_json = metadata
        self.db.add(case)
        self.repository.audit(
            action="expert_review" if expert else "engineering_review",
            target_type="retrieval_evaluation_case", target_id=str(case.id), operator=user.username,
            trace_id=trace_id, detail={"before": before, "after": after, "second_review": payload.second_review},
        )
        self.db.commit()
        self.db.refresh(case)
        return self._case_dict(case)

    def progress(self) -> dict:
        cases = self.repository.all_cases()
        counts = Counter(item.review_status for item in cases)
        categories = Counter(item.category for item in cases if item.review_status == "expert_verified")
        expert = counts.get("expert_verified", 0)
        second = sum(bool((item.metadata_json or {}).get("second_reviews")) for item in cases)
        return {
            "total": len(cases), "review_status": dict(counts), "expert_verified": expert,
            "second_reviewed": second, "second_review_ratio": second / expert if expert else 0.0,
            "categories": dict(categories),
            "vector_heavy": sum(bool((item.metadata_json or {}).get("vector_heavy")) for item in cases if item.review_status == "expert_verified"),
            "no_answer": sum(item.category == "no_answer" for item in cases if item.review_status == "expert_verified"),
            "hard_negatives": sum(bool((item.metadata_json or {}).get("hard_negative")) for item in cases if item.review_status == "expert_verified"),
            "ready_to_freeze": self._readiness(cases)[0],
            "failed_requirements": self._readiness(cases)[1],
        }

    def freeze(self, dataset_version: str, user: User) -> dict:
        if self.repository.get_freeze(dataset_version):
            raise RetrievalPilotServiceError("Dataset version already exists and cannot be overwritten")
        cases = self.repository.all_cases()
        ready, failures = self._readiness(cases)
        if not ready:
            raise RetrievalPilotServiceError("BLOCKED_EXPERT_REVIEW: " + "; ".join(failures))
        verified = [item for item in cases if item.review_status == "expert_verified"]
        frozen_rows = [
            {
                "case_id": str(item.id),
                "query_sha256": hashlib.sha256(item.query_text.encode("utf-8")).hexdigest(),
                "expected_document_ids": sorted(str(value) for value in item.expected_document_ids or []),
                "expected_chunk_ids": sorted(str(value) for value in item.expected_chunk_ids or []),
            }
            for item in verified
        ]
        dataset_sha = hashlib.sha256(
            json.dumps(frozen_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        reviewers = sorted({str((item.metadata_json or {}).get("primary_reviewer_id")) for item in verified})
        item = RetrievalDatasetFreeze(
            dataset_version=dataset_version, dataset_type="official_pilot_test",
            dataset_sha256=dataset_sha, case_count=len(verified), freeze_status="frozen",
            frozen_by=user.id, frozen_at=datetime.now(timezone.utc),
            metadata_json={
                "cases": frozen_rows, "reviewers": reviewers, "review_completion": self.progress(),
                "retrieval_config": {"modes": ["keyword", "vector", "hybrid", "adaptive_conservative", "adaptive"]},
                "collection_name": self.settings.DASHVECTOR_PHYSICAL_COLLECTION if self.settings.DASHVECTOR_USE_PARTITIONS else self.settings.DASHVECTOR_PILOT_COLLECTION,
                "partition": self.settings.DASHVECTOR_PILOT_PARTITION if self.settings.DASHVECTOR_USE_PARTITIONS else "default",
                "embedding_model": self.settings.EMBEDDING_MODEL,
                "embedding_version": self.settings.EMBEDDING_INDEX_VERSION,
            },
        )
        self.db.add(item)
        trace_id = f"r2-freeze-{uuid4().hex}"
        self.repository.audit(
            action="freeze_dataset", target_type="retrieval_dataset_freeze", target_id=dataset_version,
            operator=user.username, trace_id=trace_id, detail={"dataset_sha256": dataset_sha, "case_count": len(verified)},
        )
        self.db.commit()
        self.db.refresh(item)
        return self._freeze_dict(item)

    def list_freezes(self) -> list[dict]:
        return [self._freeze_dict(item) for item in self.repository.list_freezes()]

    def acquire_official_run_lock(self, dataset_version: str, user: User) -> dict:
        freeze = self.repository.get_freeze(dataset_version)
        if not freeze or freeze.freeze_status != "frozen":
            raise RetrievalPilotServiceError("Official dataset is not frozen")
        existing = self.repository.get_run_lock(freeze.id, self.RUN_PURPOSE)
        if existing:
            return {"status": "already_executed", "lock_id": str(existing.id), "run_id": str(existing.official_run_id) if existing.official_run_id else None}
        item = RetrievalOfficialRunLock(
            dataset_freeze_id=freeze.id, run_purpose=self.RUN_PURPOSE, lock_status="locked",
            locked_by=user.id, locked_at=datetime.now(timezone.utc), metadata_json={"dataset_sha256": freeze.dataset_sha256},
        )
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.repository.get_run_lock(freeze.id, self.RUN_PURPOSE)
            return {"status": "already_executed", "lock_id": str(existing.id) if existing else None}
        self.db.refresh(item)
        return {"status": "locked", "lock_id": str(item.id), "official_run_executed": False}

    def create_session(self, payload: PilotSessionCreate, user: User) -> dict:
        if user.role not in {"expert", "admin"}:
            raise RetrievalPilotServiceError("Only expert/admin can create Pilot sessions")
        if not self.settings.TASK25B_R2_PILOT_ENABLED:
            raise RetrievalPilotServiceError("Pilot feature is disabled")
        trace_id = f"r2-session-{uuid4().hex}"
        use_partition = bool(self.settings.DASHVECTOR_USE_PARTITIONS)
        pilot_collection = self.settings.DASHVECTOR_PHYSICAL_COLLECTION if use_partition else self.settings.DASHVECTOR_PILOT_COLLECTION
        pilot_partition = self.settings.DASHVECTOR_PILOT_PARTITION if use_partition else "default"
        metadata = {
            "session_status": "created", "scope_user_ids": [str(item) for item in payload.scope_user_ids],
            "query_prefix": payload.query_prefix, "retrieval_strategy": payload.retrieval_strategy,
            "base_collection": self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "pilot_collection": pilot_collection, "pilot_partition": pilot_partition,
            "created_by": str(user.id), "audit_trace_id": trace_id,
            "config_snapshot": {"default_strategy": self.settings.RETRIEVAL_DEFAULT_MODE, "full_reindex": self.settings.TASK25B_ALLOW_FULL_REINDEX},
        }
        item = VectorIndexRun(
            run_type="task25b_r2_pilot_session", target_type="retrieval_pilot_session",
            vector_backend="dashvector", collection_name=pilot_collection,
            namespace=pilot_partition, embedding_model=self.settings.EMBEDDING_MODEL,
            embedding_provider=self.settings.EMBEDDING_PROVIDER, status="pending",
            total_count=0, succeeded_count=0, failed_count=0, skipped_count=0,
            started_at=datetime.now(timezone.utc), metadata_json=metadata, created_by=user.id,
        )
        self.db.add(item)
        self.db.flush()
        self.repository.audit(action="create_session", target_type="pilot_session", target_id=str(item.id), operator=user.username, trace_id=trace_id, detail=metadata)
        self.db.commit()
        self.db.refresh(item)
        return self._session_dict(item)

    def activate_session(self, session_id: UUID, user: User) -> dict:
        if user.role != "admin":
            raise RetrievalPilotServiceError("Only admin can activate Pilot sessions")
        if not self.settings.TASK25B_R2_ALLOW_PILOT_SWITCH:
            raise RetrievalPilotServiceError("Pilot switch gate is disabled")
        item = self._session(session_id)
        indexed = int(
            self.db.scalar(
                select(func.count()).select_from(KnowledgeChunkVectorIndex).where(
                    KnowledgeChunkVectorIndex.collection_name == item.collection_name,
                    KnowledgeChunkVectorIndex.namespace == item.namespace,
                    KnowledgeChunkVectorIndex.index_status == "active",
                )
            ) or 0
        )
        if indexed < 300:
            raise RetrievalPilotServiceError(f"Pilot activation requires at least 300 indexed chunks; found {indexed}")
        metadata = dict(item.metadata_json or {})
        metadata.update(session_status="active", activated_by=str(user.id), activated_at=datetime.now(timezone.utc).isoformat())
        item.metadata_json = metadata
        item.status = "running"
        trace_id = str(metadata.get("audit_trace_id") or f"r2-session-{uuid4().hex}")
        self.repository.audit(action="activate_session", target_type="pilot_session", target_id=str(item.id), operator=user.username, trace_id=trace_id, detail={"scope_user_ids": metadata.get("scope_user_ids"), "query_prefix": metadata.get("query_prefix")})
        self.db.commit()
        return self._session_dict(item)

    def rollback_session(self, session_id: UUID, reason: str, user: User) -> dict:
        if user.role != "admin":
            raise RetrievalPilotServiceError("Only admin can roll back Pilot sessions")
        if not self.settings.TASK25B_R2_ALLOW_PILOT_ROLLBACK:
            raise RetrievalPilotServiceError("Pilot rollback gate is disabled")
        item = self._session(session_id)
        metadata = self.rollback_metadata(item.metadata_json or {}, user_id=user.id, reason=reason)
        item.metadata_json = metadata
        item.status = "succeeded"
        item.finished_at = datetime.now(timezone.utc)
        trace_id = str(metadata.get("audit_trace_id") or f"r2-session-{uuid4().hex}")
        self.repository.audit(action="rollback_session", target_type="pilot_session", target_id=str(item.id), operator=user.username, trace_id=trace_id, detail={"reason": reason, "base_route_restored": True})
        self.db.commit()
        return self._session_dict(item)

    def close_session(self, session_id: UUID, user: User) -> dict:
        if user.role != "admin":
            raise RetrievalPilotServiceError("Only admin can close Pilot sessions")
        item = self._session(session_id)
        metadata = dict(item.metadata_json or {})
        metadata.update(session_status="closed", closed_by=str(user.id), closed_at=datetime.now(timezone.utc).isoformat())
        item.metadata_json = metadata
        item.status = "succeeded"
        item.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        return self._session_dict(item)

    def get_session(self, session_id: UUID) -> dict:
        return self._session_dict(self._session(session_id))

    def route_for(self, user: User, question: str) -> PilotRouteDecision:
        for session in self.repository.active_sessions():
            metadata = session.metadata_json or {}
            scoped = str(user.id) in set(metadata.get("scope_user_ids") or [])
            prefixed = bool(question.startswith(str(metadata.get("query_prefix") or "Task25BR2_")))
            if scoped or (prefixed and user.role in {"expert", "admin"}):
                return PilotRouteDecision(
                    active=True, session_id=session.id, collection=session.collection_name,
                    retrieval_strategy=str(metadata.get("retrieval_strategy") or "adaptive"),
                    audit_trace_id=str(metadata.get("audit_trace_id") or ""), reason="scoped_pilot_session",
                    metadata={"scope_match": scoped, "prefix_match": prefixed, "partition": getattr(session, "namespace", "default")},
                )
        return PilotRouteDecision(collection=self.settings.DASHVECTOR_PHYSICAL_COLLECTION)

    def _session(self, session_id: UUID | str) -> VectorIndexRun:
        resolved_id = session_id if isinstance(session_id, UUID) else UUID(str(session_id))
        item = self.repository.get_session(resolved_id)
        if not item:
            raise RetrievalPilotServiceError("Pilot session not found")
        return item

    def _ensure_not_frozen(self, case_id: UUID) -> None:
        for freeze in self.repository.list_freezes():
            if freeze.freeze_status != "frozen":
                continue
            frozen_ids = {str(item.get("case_id")) for item in (freeze.metadata_json or {}).get("cases", [])}
            if str(case_id) in frozen_ids:
                raise RetrievalPilotServiceError("Frozen benchmark labels cannot be silently modified")

    @staticmethod
    def _readiness(cases: list[RetrievalEvaluationCase]) -> tuple[bool, list[str]]:
        verified = [item for item in cases if item.review_status == "expert_verified"]
        second = sum(bool((item.metadata_json or {}).get("second_reviews")) for item in verified)
        failures = []
        if len(verified) < 100:
            failures.append(f"expert_verified {len(verified)}/100")
        if second < max(20, int(len(verified) * 0.2)):
            failures.append(f"second_reviewed {second}/20")
        if sum(item.category == "no_answer" for item in verified) < 15:
            failures.append("no_answer below 15")
        if sum(bool((item.metadata_json or {}).get("vector_heavy")) for item in verified) < 20:
            failures.append("vector_heavy below 20")
        if sum(bool((item.metadata_json or {}).get("hard_negative")) for item in verified) < 15:
            failures.append("hard_negative below 15")
        if sum(item.category == "safety_procedure" for item in verified) < 10:
            failures.append("safety_procedure below 10")
        if sum(item.category == "multimodal_descriptor" for item in verified) < 10:
            failures.append("multimodal_descriptor below 10")
        return not failures, failures

    @staticmethod
    def allowed_review_roles(*, expert: bool) -> set[str]:
        return {"expert", "admin"} if expert else {"engineer", "expert", "admin"}

    @staticmethod
    def rollback_metadata(metadata: dict, *, user_id: UUID, reason: str) -> dict:
        result = dict(metadata)
        result.update(
            session_status="rolled_back", rolled_back_by=str(user_id),
            rolled_back_at=datetime.now(timezone.utc).isoformat(), rollback_reason=reason,
            base_route_restored=True,
        )
        return result

    @staticmethod
    def _case_dict(item: RetrievalEvaluationCase) -> dict:
        metadata = item.metadata_json or {}
        return {
            "id": str(item.id), "name": item.name, "category": item.category,
            "query_text": item.query_text, "expected_document_ids": item.expected_document_ids,
            "expected_chunk_ids": item.expected_chunk_ids, "difficulty": item.difficulty,
            "dataset_split": item.dataset_split, "review_status": item.review_status,
            "vector_heavy": bool(metadata.get("vector_heavy")), "lexical_easy": bool(metadata.get("lexical_easy")),
            "no_answer": item.category == "no_answer", "source_locator": metadata.get("source_locator"),
            "source_excerpt": metadata.get("source_excerpt"),
            "source_provenance": metadata.get("source_provenance"),
            "review_history": metadata.get("review_history") or [], "second_reviews": metadata.get("second_reviews") or [],
            "query_sha256": hashlib.sha256(item.query_text.encode("utf-8")).hexdigest(),
        }

    @staticmethod
    def _freeze_dict(item: RetrievalDatasetFreeze) -> dict:
        return {
            "id": str(item.id), "dataset_version": item.dataset_version, "dataset_type": item.dataset_type,
            "dataset_sha256": item.dataset_sha256, "case_count": item.case_count,
            "freeze_status": item.freeze_status, "frozen_by": str(item.frozen_by), "frozen_at": item.frozen_at,
            "unfrozen": item.freeze_status != "frozen",
        }

    @staticmethod
    def _session_dict(item: VectorIndexRun) -> dict:
        metadata = item.metadata_json or {}
        return {
            "session_id": str(item.id), "pilot_collection": item.collection_name,
            "pilot_partition": item.namespace,
            "base_collection": metadata.get("base_collection"), "retrieval_strategy": metadata.get("retrieval_strategy"),
            "created_by": str(item.created_by) if item.created_by else None,
            "activated_by": metadata.get("activated_by"), "activated_at": metadata.get("activated_at"),
            "rolled_back_by": metadata.get("rolled_back_by"), "rolled_back_at": metadata.get("rolled_back_at"),
            "rollback_reason": metadata.get("rollback_reason"), "status": metadata.get("session_status"),
            "scope_user_ids": metadata.get("scope_user_ids") or [], "query_prefix": metadata.get("query_prefix"),
            "config_snapshot": metadata.get("config_snapshot"), "result_summary": metadata.get("result_summary"),
            "audit_trace_id": metadata.get("audit_trace_id"),
        }
