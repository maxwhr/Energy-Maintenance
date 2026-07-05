from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from app.api.routes.media import router as media_router
from app.api.routes.model_gateway import router as model_gateway_router
from app.api.routes.multimodal_evidence import router as multimodal_evidence_router
from app.api.routes.record_center import router as record_center_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.review import router as review_router
from app.api.routes.sop import router as sop_router
from app.api.routes.system import router as system_router
from app.api.routes.users import router as users_router
from app.api.routes.vector_search import router as vector_search_router
from app.core.config import get_settings
from app.core.security_config import enforce_startup_security
from app.core.security_middleware import InMemoryRateLimitMiddleware, RequestSizeLimitMiddleware
from app.core.static_frontend import register_static_frontend

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Huawei and Sungrow PV inverter maintenance knowledge retrieval and work-assistance system.",
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


@app.on_event("startup")
async def validate_startup_security() -> None:
    enforce_startup_security(settings)

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(vector_search_router)
api_router.include_router(auth_router)
api_router.include_router(agents_router)
api_router.include_router(users_router)
api_router.include_router(devices_router)
api_router.include_router(external_apis_router)
api_router.include_router(knowledge_router)
api_router.include_router(knowledge_contributions_router)
api_router.include_router(knowledge_graph_router)
api_router.include_router(maintenance_tasks_router)
api_router.include_router(media_router)
api_router.include_router(model_gateway_router)
api_router.include_router(multimodal_evidence_router)
api_router.include_router(retrieval_router)
api_router.include_router(diagnosis_router)
api_router.include_router(sop_router)
api_router.include_router(record_center_router)
api_router.include_router(review_router)
api_router.include_router(corrections_router)

app.include_router(api_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message", "data"}.issubset(exc.detail):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "Request validation failed",
            "data": exc.errors(),
        },
    )


register_static_frontend(app)
