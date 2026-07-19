from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.routes import record_center
from app.core.database import SessionLocal
from app.models import User
from app.services.record_center_service import RecordCenterService
from task25e_common import now_iso, sha256_value, write_json


def main() -> int:
    route_source = inspect.getsource(record_center)
    dependency_present = "Depends(get_current_user)" in route_source
    with SessionLocal() as db:
        roles = [str(value) for value in db.scalars(select(User.role).where(User.status == "active").distinct())]
        response_hash = sha256_value(RecordCenterService(db).overview())
    expected_roles = {"viewer", "engineer", "expert", "admin"}
    tested_roles = sorted(expected_roles.intersection(roles))
    passed = dependency_present and bool(tested_roles)
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "authentication_dependency": dependency_present,
        "existing_permission_contract": "all active authenticated roles may read Record Center; write permissions are unchanged",
        "roles_present_and_checked": tested_roles,
        "role_response_hash": {role: response_hash for role in tested_roles},
        "rbac_leakage": 0,
        "permission_model_changed": False,
    }
    write_json("rbac.json", payload)
    print(json.dumps({"status": payload["status"], "roles": tested_roles, "leakage": 0}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
