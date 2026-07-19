import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.rerank_adapters.qwen3_rerank_adapter import Qwen3RerankAdapter
from tests.r5_r6_test_helpers import qwen_settings


def test_missing_workspace_base_url_is_explicit_config_error() -> None:
    settings = qwen_settings(DASHSCOPE_RERANK_BASE_URL="")
    assert Qwen3RerankAdapter(settings)._configuration_error() == "QWEN3_RERANK_CONFIG_MISSING"


def test_document_limit_is_bounded_to_20_50() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DASHSCOPE_RERANK_MAX_DOCUMENTS=51)
