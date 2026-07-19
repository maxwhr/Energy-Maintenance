from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.schemas.retrieval_scope import RetrievalScope


def test_retrieval_scope_is_immutable_and_explicit():
    scope = RetrievalScope("s", "pilot", "zh-CN", (uuid4(),), "approved", "active",
                           ("development_engineering_auto",), True, True, "collection", "pilot_r2")
    assert scope.public_dict()["partition_name"] == "pilot_r2"
    with pytest.raises((FrozenInstanceError, AttributeError)):
        scope.scope_id = "expanded"  # type: ignore[misc]
