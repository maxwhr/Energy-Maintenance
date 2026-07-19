from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import QueryAwareRetrievalSession, User
from app.repositories.query_aware_retrieval_repository import QueryAwareRetrievalRepository
from app.schemas.query_understanding import ClarificationDecision, QuerySignals


class ConversationContextError(ValueError):
    pass


class ConversationRetrievalContextService:
    TTL_HOURS = 24
    FACT_KEYS = (
        "device_models", "alarm_codes", "alarm_names", "components", "time_conditions", "operating_states", "numbers",
        "negative_expressions", "communication_terms", "symptoms", "requested_information",
    )
    SCALAR_FACT_KEYS = (
        "manufacturer", "product_family", "model", "model_original", "alarm_code",
        "fault_type", "maintenance_intent", "safety_risk",
    )

    def __init__(self, db: Session):
        self.db = db
        self.repository = QueryAwareRetrievalRepository(db)

    def create(
        self,
        *,
        original_query: str,
        signals: QuerySignals,
        clarification: ClarificationDecision,
        current_user: User,
    ) -> QueryAwareRetrievalSession:
        conversation_id = f"qar-{uuid4().hex}"
        state = {
            "original_query": original_query,
            "previous_questions": list(clarification.questions),
            "user_clarifications": [],
            "merged_confirmed_facts": self._fact_dict(signals),
            "merged_query": signals.normalized_query,
            "unresolved_missing_information": list(clarification.missing_information),
            "hypotheses": [],
        }
        item = QueryAwareRetrievalSession(
            conversation_id=conversation_id,
            original_query=original_query,
            state_json=state,
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.TTL_HOURS),
            created_by=current_user.id,
        )
        self.repository.save(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def merge(
        self,
        *,
        conversation_id: str,
        clarification_text: str,
        clarification_signals: QuerySignals,
        current_user: User,
    ) -> QueryAwareRetrievalSession:
        item = self.repository.get_active(conversation_id, created_by=current_user.id)
        if item is None:
            raise ConversationContextError("retrieval conversation not found or expired")
        state = dict(item.state_json or {})
        facts = dict(state.get("merged_confirmed_facts") or {})
        new_facts = self._fact_dict(clarification_signals)
        for key in self.FACT_KEYS:
            facts[key] = list(dict.fromkeys([*(facts.get(key) or []), *(new_facts.get(key) or [])]))
        for key in self.SCALAR_FACT_KEYS:
            if new_facts.get(key) is not None:
                facts[key] = new_facts[key]
        unresolved = [value for value in (state.get("unresolved_missing_information") or []) if not self._resolved(value, facts)]
        clarifications = [*(state.get("user_clarifications") or []), clarification_text]
        state.update({
            "user_clarifications": clarifications,
            "merged_confirmed_facts": facts,
            "merged_query": " ".join([item.original_query, *clarifications]).strip(),
            "unresolved_missing_information": unresolved,
            "hypotheses": [],
        })
        item.state_json = state
        item.expires_at = datetime.now(timezone.utc) + timedelta(hours=self.TTL_HOURS)
        self.repository.save(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get(self, conversation_id: str, *, current_user: User) -> QueryAwareRetrievalSession:
        item = self.repository.get_active(conversation_id, created_by=current_user.id)
        if item is None:
            raise ConversationContextError("retrieval conversation not found or expired")
        return item

    def restart(self, conversation_id: str, *, current_user: User) -> None:
        item = self.repository.get(conversation_id, created_by=current_user.id)
        if item is None:
            raise ConversationContextError("retrieval conversation not found")
        item.status = "closed"
        self.repository.save(item)
        self.db.commit()

    @classmethod
    def _fact_dict(cls, signals: QuerySignals) -> dict:
        values = {key: list(getattr(signals, key)) for key in cls.FACT_KEYS}
        values.update({key: getattr(signals, key) for key in cls.SCALAR_FACT_KEYS})
        return values

    @staticmethod
    def _resolved(key: str, facts: dict) -> bool:
        mapping = {
            "device_model": "device_models",
            "specific_symptom_or_alarm_code": "symptoms",
            "requested_information": "requested_information",
            "component": "components",
            "communication_method": "communication_terms",
            "occurrence_condition": "time_conditions",
        }
        if key == "specific_symptom_or_alarm_code":
            return bool(facts.get("symptoms") or facts.get("alarm_codes"))
        return bool(facts.get(mapping.get(key, key)))
