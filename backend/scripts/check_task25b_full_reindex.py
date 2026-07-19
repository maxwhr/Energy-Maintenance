from __future__ import annotations

import argparse
from sqlalchemy import select

from task25b_common import write_result
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.services.vector_index_service import VectorIndexService, VectorIndexServiceError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not (args.execute and args.allow_real_api and settings.TASK25B_ALLOW_FULL_REINDEX):
        write_result("full_reindex.json", {"status": "BLOCKED_BY_GATE", "full_reindex_allowed": settings.TASK25B_ALLOW_FULL_REINDEX, "external_api_called": False})
        return 2
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        try:
            result = VectorIndexService(db, allow_real_api=True).reindex_approved(current_user=user, dry_run=False, test_only=False, limit=5000)
        except VectorIndexServiceError as exc:
            result = {"status": "FAILED", "reason": str(exc)}
    write_result("full_reindex.json", result)
    return 0 if result.get("status") != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
