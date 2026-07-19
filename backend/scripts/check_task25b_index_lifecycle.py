from __future__ import annotations

import argparse
from sqlalchemy import select

from task25b_common import write_result
from app.core.database import SessionLocal
from app.models import User
from app.services.vector_index_service import VectorIndexService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--execute-test-only", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        service = VectorIndexService(db, allow_real_api=args.allow_real_api)
        report = service.lifecycle_report()
        result = {"status": "PASSED", "dry_run": not args.execute_test_only, "test_only": True, **report}
        if args.execute_test_only:
            user = db.scalar(select(User).where(User.role == "admin"))
            if not user:
                result.update({"status": "BLOCKED", "reason": "admin user not found"})
            else:
                result["execution"] = service.reindex_approved(current_user=user, dry_run=False, test_only=True, limit=200)
    write_result("index_lifecycle.json", result)
    return 0 if result["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
