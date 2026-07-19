import pytest

from app.core.database import SessionLocal
from scripts.task25b_r1_eval_common import load_cases


def test_tuning_guard_refuses_test_v2_labels():
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="frozen"):
            load_cases(db, "test_v2", allow_blind=False)
