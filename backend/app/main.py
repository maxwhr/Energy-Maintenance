from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.corrections import router as corrections_router
from app.api.routes.diagnosis import router as diagnosis_router
from app.api.routes.devices import router as devices_router
from app.api.routes.external_apis import router as external_apis_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.knowledge_contributions import router as knowledge_contributions_router
from app.api.routes.knowledge_graph import router as knowledge_graph_router
from app.api.routes.maintenance_tasks import router as maintenance_tasks_router
from app.api.routes.maintenance_workflows import router as maintenance_workflows_router
from app.api.routes.media import router as media_router
from app.api.routes.model_gateway import router as model_gateway_router
from app.api.routes.multimodal_evidence import router as multimodal_evidence_router
from app.api.routes.multimodal_cases import router as multimodal_cases_router
from app.api.routes.record_center import router as record_center_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.review import router as review_router
from app.api.routes.sop import router as sop_router
from app.api.routes.system import router as system_router
from app.api.routes.users import router as users_router
from app.api.routes.vector_search import router as vector_search_router
from app.core.config import get_settings
from app.core.exceptions import (
    BusinessException,
    business_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.retrieval_lab_config import get_retrieval_lab_settings
from app.core.security_config import enforce_startup_security
from app.core.security_middleware import InMemoryRateLimitMiddleware, RequestSizeLimitMiddleware
from app.core.static_frontend import register_static_frontend
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    enforce_startup_security(settings)
    try:
        yield
    finally:
        MiniMaxAnthropicAdapter.close_shared()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Huawei and Sungrow PV inverter maintenance knowledge retrieval and work-assistance system.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)
app.add_middleware(InMemoryRateLimitMiddleware, settings=settings)
app.add_middleware(RequestSizeLimitMiddleware, settings=settings)

def create_api_router(*, retrieval_lab_enabled: bool) -> APIRouter:
    router = APIRouter(prefix="/api")
    router.include_router(health_router)
    router.include_router(system_router)
    router.include_router(vector_search_router)
    router.include_router(auth_router)
    router.include_router(agents_router)
    router.include_router(users_router)
    router.include_router(devices_router)
    router.include_router(external_apis_router)
    router.include_router(knowledge_router)
    router.include_router(knowledge_contributions_router)
    router.include_router(knowledge_graph_router)
    router.include_router(maintenance_tasks_router)
    router.include_router(maintenance_workflows_router)
    router.include_router(media_router)
    router.include_router(model_gateway_router)
    router.include_router(multimodal_evidence_router)
    router.include_router(multimodal_cases_router)
    router.include_router(retrieval_router)
    router.include_router(diagnosis_router)
    router.include_router(sop_router)
    router.include_router(record_center_router)
    router.include_router(review_router)
    router.include_router(corrections_router)
    if retrieval_lab_enabled:
        from app.api.routes.retrieval_lab import router as retrieval_lab_router

        router.include_router(retrieval_lab_router)
    return router


api_router = create_api_router(
    retrieval_lab_enabled=(
        get_retrieval_lab_settings().ENABLE_RETRIEVAL_LAB
    )
)

app.include_router(api_router)

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


register_static_frontend(app)
