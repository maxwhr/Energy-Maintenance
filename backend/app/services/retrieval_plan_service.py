from __future__ import annotations

from app.core.config import get_settings
from app.schemas.query_understanding import ClarificationDecision, QueryUnderstandingResult
from app.schemas.retrieval_plan import RetrievalPlan
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.deterministic_query_expansion_service import DeterministicQueryExpansionService


class IntentAnchorCoverageMatrix:
    VERSION = "task25b_r3_dev_r5_r5_anchor_matrix_v1"
    MATRIX = {
        "CAUSE": ["CAUSE", "SYMPTOM", "ALARM", "FULL_SECTION"],
        "ACTION": ["ACTION", "PROCEDURE", "ALARM", "SAFETY", "VERIFICATION", "FULL_SECTION"],
        "PROCEDURE": ["PROCEDURE", "ACTION", "PREREQUISITE", "SAFETY", "VERIFICATION", "FULL_SECTION"],
        "SAFETY": ["SAFETY", "PROCEDURE", "ACTION", "FULL_SECTION"],
        "ALARM_MEANING": ["ALARM", "SYMPTOM", "CAUSE", "ACTION", "FULL_SECTION"],
        "PREREQUISITE": ["PREREQUISITE", "PROCEDURE", "SAFETY", "FULL_SECTION"],
        "VERIFICATION": ["VERIFICATION", "PROCEDURE", "ACTION", "ALARM", "FULL_SECTION"],
        "CONFIGURATION": ["PROCEDURE", "PREREQUISITE", "ACTION", "VERIFICATION", "FULL_SECTION"],
        "GENERAL_INFORMATION": ["SYMPTOM", "ACTION", "PROCEDURE", "FULL_SECTION"],
        "COMMUNICATION": ["COMMUNICATION", "SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "VERIFICATION", "FULL_SECTION"],
        "TROUBLESHOOTING": ["SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "ALARM", "SAFETY", "FULL_SECTION"],
    }

    @classmethod
    def resolve(cls, primary_intent: str, requested_information: list[str]) -> list[str]:
        output: list[str] = []
        for key in [primary_intent, *requested_information]:
            output.extend(cls.MATRIX.get(key, []))
        output = list(dict.fromkeys(output or cls.MATRIX["GENERAL_INFORMATION"]))
        if "FULL_SECTION" in output:
            output = [value for value in output if value != "FULL_SECTION"] + ["FULL_SECTION"]
        return output


class RetrievalPlanService:
    VERSION = "task25b_r3_dev_r5_r5_planner_v3"
    CHANNEL_BUDGETS = {
        "EXACT_KEYWORD": 30,
        "SCOPED_KEYWORD": 80,
        "RAW_VECTOR": 80,
        "SEMANTIC_UNIT": 100,
    }

    def build(
        self,
        understanding: QueryUnderstandingResult,
        *,
        clarification: ClarificationDecision,
        candidate_top_k: int = 50,
        required_scope: str = CHINESE_ENGINEERING_PILOT_SCOPE_ID,
    ) -> RetrievalPlan:
        settings = get_settings()
        variants = DeterministicQueryExpansionService().expand(understanding)
        explicit_models = [
            value for value in understanding.device_models
            if "".join(character for character in value.upper() if character.isalnum()) != "SUN2000"
        ]
        explicit = [*explicit_models, *understanding.alarm_codes, *understanding.alarm_names]
        channels = ["SCOPED_KEYWORD"] if understanding.fast_path else ["SCOPED_KEYWORD", "RAW_VECTOR", "SEMANTIC_UNIT"]
        if explicit:
            channels.insert(0, "EXACT_KEYWORD")
        all_queries = [item.query for item in variants]
        vector_queries = [
            item.query for item in variants
            if item.variant_type in {"ORIGINAL", "REQUEST_QUERY"}
        ][:2]
        channel_queries = {channel: list(all_queries) for channel in channels}
        if "EXACT_KEYWORD" in channel_queries:
            channel_queries["EXACT_KEYWORD"] = list(dict.fromkeys(explicit))
        if "RAW_VECTOR" in channel_queries:
            channel_queries["RAW_VECTOR"] = vector_queries or [understanding.normalized_query]
        if "SEMANTIC_UNIT" in channel_queries:
            request_queries = [
                item.query for item in variants if item.variant_type == "REQUEST_QUERY"
            ]
            channel_queries["SEMANTIC_UNIT"] = request_queries[:1] or [understanding.normalized_query]
        weights = {
            "EXACT_KEYWORD": 1.0,
            "SCOPED_KEYWORD": 0.9,
            "RAW_VECTOR": 0.85,
            "SEMANTIC_UNIT": 1.0,
        }
        query_weights = {
            "ORIGINAL": settings.RAG_QUERY_WEIGHT_ORIGINAL,
            "CANONICAL": settings.RAG_QUERY_WEIGHT_CANONICAL,
            "SYMPTOM_QUERY": 0.86,
            "REQUEST_QUERY": settings.RAG_QUERY_WEIGHT_INTENT,
            "CONDITION_QUERY": settings.RAG_QUERY_WEIGHT_CONDITION,
        }
        anchors = IntentAnchorCoverageMatrix.resolve(
            understanding.primary_intent, list(understanding.requested_information)
        )
        return RetrievalPlan(
            original_query=understanding.original_query,
            canonical_query=understanding.canonical_question,
            query_variants=variants,
            requested_channels=channels,
            channel_queries=channel_queries,
            channel_weights={key: weights[key] for key in channels},
            query_weights=query_weights,
            anchor_types=anchors,
            anchor_matrix_version=IntentAnchorCoverageMatrix.VERSION,
            channel_candidate_budgets={key: self.CHANNEL_BUDGETS[key] for key in channels},
            per_channel_identity_limit=60,
            fusion_candidate_limit=150,
            candidate_top_k=candidate_top_k,
            rerank_required=clarification.status != "CLARIFICATION_REQUIRED",
            clarification_policy=clarification.status,
            required_scope=required_scope,
            fallback_policy="KEEP_SCOPE_AND_PRESERVE_RRF",
            fast_path=understanding.fast_path,
            kg_alias_status="DISABLED_DUPLICATE_KEYWORD",
        )
