from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.sql.elements import False_

from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import HUAWEI_SUN2000_COMPETITION_SCOPE_ID
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.retrieval_scope_service import RetrievalScopeService


def _document(**overrides):
    values = {
        "id": uuid4(),
        "title": "华为 SUN2000 光伏逆变器维护手册",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "model": "SUN2000-100KTL-M1",
        "device_type": "pv_inverter",
        "source_type": "vendor_official",
        "status": "active",
        "parse_status": "parsed",
        "review_status": "approved",
        "metadata_json": {
            "normalized_language": "zh-CN",
            "is_current_version": True,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_huawei_sun2000_and_relevant_fusionsolar_documents_are_included() -> None:
    assert RetrievalScopeService.is_huawei_sun2000_document_eligible(_document())
    assert RetrievalScopeService.is_huawei_sun2000_document_eligible(_document(
        title="FusionSolar 华为逆变器夜间通信维护说明",
        product_series="FusionSolar",
        model=None,
    ))


def test_reviewed_huawei_contribution_requires_explicit_human_or_competition_approval() -> None:
    assert not RetrievalScopeService.is_huawei_sun2000_document_eligible(_document(
        source_type="knowledge_contribution",
    ))
    assert RetrievalScopeService.is_huawei_sun2000_document_eligible(_document(
        source_type="knowledge_contribution",
        metadata_json={
            "normalized_language": "zh-CN",
            "is_current_version": True,
            "competition_approved": True,
        },
    ))


def test_formal_scope_excludes_products_states_languages_and_test_material() -> None:
    excluded = (
        _document(manufacturer="sungrow", product_series="SG"),
        _document(title="华为 LUNA2000 储能维护手册", model="LUNA2000-S1"),
        _document(title="SmartLogger 独立维护手册", model="SmartLogger3000"),
        _document(status="archived"),
        _document(parse_status="failed"),
        _document(review_status="pending"),
        _document(review_status="rejected"),
        _document(product_series="Other"),
        _document(metadata_json={"normalized_language": "en-US", "is_current_version": True}),
        _document(metadata_json={"normalized_language": "zh-CN", "is_test_fixture": True}),
        _document(metadata_json={"normalized_language": "zh-CN", "is_current_version": False}),
        _document(title="Task25 fixture SUN2000 negative sample"),
        _document(source_type="ai_generated"),
    )
    assert all(not RetrievalScopeService.is_huawei_sun2000_document_eligible(item) for item in excluded)


class _EmptyScalarSession:
    def scalars(self, _statement):
        return []


def test_empty_competition_scope_is_safe_and_repository_adds_false_filter() -> None:
    scope = RetrievalScopeService(_EmptyScalarSession()).resolve(
        HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
        pilot_required=True,
    )
    assert scope is not None
    assert scope.allowed_document_ids == ()
    filters = RetrievalRepository._scope_filters(scope)
    assert len(filters) == 1
    assert isinstance(filters[0], False_)


def test_query_aware_formal_scope_constant_matches_public_competition_scope() -> None:
    assert QueryAwareRetrievalService.FORMAL_SCOPE_ID == HUAWEI_SUN2000_COMPETITION_SCOPE_ID
