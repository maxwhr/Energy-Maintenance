from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.model_gateway import ModelGatewayChatRequest, ModelMessage
from app.services.model_gateway_service import ModelGatewayService, ModelGatewayServiceError


ALLOWED_ENHANCEMENT_PROVIDERS = {"rule_based", "local_llama_cpp", "cloud_openai"}


@dataclass(slots=True)
class EnhancementResult:
    content: str | None
    model_enhanced: bool
    fallback_used: bool
    model_provider: str
    model_name: str
    model_call_trace_id: str | None
    error_message: str | None = None


class ModelEnhancementService:
    def __init__(self, db: Session):
        self.gateway = ModelGatewayService(db)

    def enhance(
        self,
        *,
        prompt: str,
        task_type: str,
        requested_provider: str | None,
        allow_fallback: bool,
        current_user: User,
        default_provider: str,
        default_model_name: str,
    ) -> EnhancementResult:
        provider = self._normalize_provider(requested_provider)
        forced_viewer_fallback = False
        if current_user.role == "viewer" and provider != "rule_based":
            provider = "rule_based"
            forced_viewer_fallback = True
        bounded_prompt = self._bounded_prompt(prompt)

        try:
            gateway_response = self.gateway.chat(
                ModelGatewayChatRequest(
                    provider=provider,  # type: ignore[arg-type]
                    task_type=task_type,  # type: ignore[arg-type]
                    allow_fallback=allow_fallback,
                    messages=[
                        ModelMessage(
                            role="system",
                            content=(
                                "你是华为与阳光电源光伏逆变器检修作业辅助模型。"
                                "必须严格基于用户提供的规则结果和真实来源，不得编造 references。"
                            ),
                        ),
                        ModelMessage(role="user", content=bounded_prompt),
                    ],
                ),
                current_user,
            )
        except (ModelGatewayServiceError, ValueError) as exc:
            return EnhancementResult(
                content=None,
                model_enhanced=False,
                fallback_used=allow_fallback,
                model_provider=default_provider,
                model_name=default_model_name,
                model_call_trace_id=None,
                error_message=str(exc),
            )

        if not gateway_response.success or not gateway_response.content.strip():
            return EnhancementResult(
                content=None,
                model_enhanced=False,
                fallback_used=gateway_response.fallback_used or forced_viewer_fallback,
                model_provider=default_provider,
                model_name=default_model_name,
                model_call_trace_id=gateway_response.trace_id,
                error_message=gateway_response.error_message,
            )

        return EnhancementResult(
            content=gateway_response.content.strip(),
            model_enhanced=True,
            fallback_used=gateway_response.fallback_used or forced_viewer_fallback,
            model_provider=gateway_response.provider,
            model_name=gateway_response.model_name,
            model_call_trace_id=gateway_response.trace_id,
            error_message=gateway_response.error_message,
        )

    @staticmethod
    def apply_metadata(target: Any, enhancement: EnhancementResult) -> None:
        target.model_enhanced = enhancement.model_enhanced
        target.fallback_used = enhancement.fallback_used
        target.model_provider = enhancement.model_provider
        target.model_name = enhancement.model_name
        target.model_call_trace_id = enhancement.model_call_trace_id

    @staticmethod
    def _normalize_provider(provider: str | None) -> str:
        if provider in ALLOWED_ENHANCEMENT_PROVIDERS:
            return provider
        return "rule_based"

    @staticmethod
    def _bounded_prompt(prompt: str, limit: int = 7800) -> str:
        stripped = prompt.strip()
        if len(stripped) <= limit:
            return stripped
        head_limit = int(limit * 0.62)
        tail_limit = limit - head_limit - 120
        return (
            stripped[:head_limit]
            + "\n\n[Prompt truncated for model gateway safety; traceable evidence was summarized.]\n\n"
            + stripped[-tail_limit:]
        )
