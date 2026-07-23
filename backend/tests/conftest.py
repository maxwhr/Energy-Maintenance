from __future__ import annotations

import os
import socket
import sys
from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Settings resolves env_file relative to the current working directory. Running
# from this directory guarantees that backend/.env is never consulted by tests.
os.chdir(TESTS_DIR)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is required and must point to a disposable PostgreSQL database"
    )

parsed_test_url = make_url(TEST_DATABASE_URL)
if parsed_test_url.get_backend_name() != "postgresql":
    raise RuntimeError("Tests require a disposable PostgreSQL database")
if parsed_test_url.database in {None, "", "energy_maintenance"}:
    raise RuntimeError("Refusing to use the formal energy_maintenance database")

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "SECRET_KEY": "local-ci-only-signing-secret-32-characters",
        "SECURITY_REQUIRE_STRONG_PRODUCTION_CONFIG": "false",
        "RATE_LIMIT_ENABLED": "false",
        "ENABLE_RETRIEVAL_LAB": "false",
        "MODEL_GATEWAY_DEFAULT_PROVIDER": "rule_based",
        "EXTERNAL_REAL_CALLS_ENABLED": "false",
        "CLOUD_LLM_ENABLED": "false",
        "CLOUD_VISION_ENABLED": "false",
        "OCR_API_ENABLED": "false",
        "OCR_ENABLED": "false",
        "EMBEDDING_ENABLED": "false",
        "EMBEDDING_REAL_CALL_ENABLED": "false",
        "DASHVECTOR_ENABLED": "false",
        "DASHVECTOR_REAL_CALL_ENABLED": "false",
        "VECTOR_SEARCH_ENABLED": "false",
        "RERANK_ENABLED": "false",
        "DASHSCOPE_RERANK_ENABLED": "false",
        "MIMO_ENABLED": "false",
        "MINIMAX_ENABLED": "false",
        "RAG_OPTIONAL_LLM_TIEBREAK_ENABLED": "false",
        "RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED": "false",
    }
)
for secret_name in (
    "CLOUD_LLM_API_KEY",
    "CLOUD_VISION_API_KEY",
    "OCR_API_KEY",
    "EMBEDDING_API_KEY",
    "DASHVECTOR_API_KEY",
    "RERANK_API_KEY",
    "DASHSCOPE_API_KEY",
    "MIMO_API_KEY",
    "MINIMAX_API_KEY",
):
    os.environ[secret_name] = ""

from app import models as _models  # noqa: E402,F401
from app.core.database import engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, User  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def disposable_database() -> Generator[None, None, None]:
    with engine.connect() as connection:
        identity = connection.execute(
            text("SELECT current_database(), inet_server_port()")
        ).one()
        if identity[0] == "energy_maintenance":
            raise RuntimeError("Refusing to run tests against the formal database")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    original = socket.create_connection

    def local_only(address, *args, **kwargs):
        host = str(address[0]).lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise AssertionError(f"External network access is disabled in tests: {host}")
        return original(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", local_only)


@pytest.fixture
def db_session(disposable_database: None) -> Generator[Session, None, None]:
    connection = engine.connect()
    outer_transaction = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def factory(
        *,
        username: str,
        role: str,
        password: str = "LocalOnly!234",
        status: str = "active",
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=f"{role.title()} User",
            role=role,
            status=status,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.flush()
        return user

    return factory


@pytest.fixture
def admin_user(make_user: Callable[..., User]) -> User:
    return make_user(username="test_admin", role="admin")


@pytest.fixture
def approved_document(
    db_session: Session,
) -> Callable[..., tuple[KnowledgeDocument, KnowledgeChunk]]:
    def factory(
        *,
        manufacturer: str = "huawei",
        product_series: str = "SUN2000",
        title: str | None = None,
        content: str | None = None,
        review_status: str = "approved",
        chunk_status: str = "active",
    ) -> tuple[KnowledgeDocument, KnowledgeChunk]:
        resolved_title = title or f"{product_series} maintenance manual"
        resolved_content = content or (
            f"{manufacturer} {product_series} inverter low insulation resistance. "
            "Check DC side cable damage with an insulation resistance tester and power off."
        )
        document = KnowledgeDocument(
            title=resolved_title,
            manufacturer=manufacturer,
            product_series=product_series,
            model=f"{product_series}-TEST",
            device_type="pv_inverter",
            document_type="manual",
            source="https://vendor.example/manual",
            source_type="vendor_official",
            file_name=f"{product_series.lower()}-manual.txt",
            file_ext="txt",
            parse_status="parsed",
            chunk_count=1,
            summary=resolved_content,
            metadata_json={
                "normalized_language": "zh-CN",
                "is_default_retrieval_language": "true",
                "is_current_version": "true",
                "is_test_fixture": "false",
                "marketing_only": "false",
                "quality_status": "APPROVED",
            },
            review_status=review_status,
            status="active",
        )
        db_session.add(document)
        db_session.flush()
        chunk = KnowledgeChunk(
            document_id=document.id,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type="pv_inverter",
            document_type="manual",
            chunk_index=0,
            content=resolved_content,
            content_hash=f"{manufacturer}-{product_series}-chunk",
            section_title="Fault handling",
            char_count=len(resolved_content),
            page_number=1,
            metadata_json={"source_locator": {"section": "Fault handling"}},
            status=chunk_status,
        )
        db_session.add(chunk)
        db_session.flush()
        return document, chunk

    return factory
