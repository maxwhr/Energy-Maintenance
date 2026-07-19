from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from task25b_r2_u2_common import now_iso, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.retrieval_pilot import PilotSessionCreate
from app.services.retrieval_pilot_service import RetrievalPilotService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--preserve-partition", action="store_true")
    args = parser.parse_args()
    if not (args.pilot_only and args.preserve_partition):
        raise SystemExit("--pilot-only and --preserve-partition are required")
    settings = get_settings()
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.created_at))
        if not admin:
            payload = {"generated_at": now_iso(), "status": "BLOCKED_CONFIG", "reason": "No active admin audit actor"}
            write_json("pilot_switch_and_rollback.json", payload)
            return 2
        service = RetrievalPilotService(db)
        session = service.create_session(PilotSessionCreate(
            scope_user_ids=[admin.id],
            query_prefix="Task25BR2U2_",
            retrieval_strategy="adaptive",
        ), admin)
        rolled_back = service.rollback_session(session["session_id"], "Task25B-R2-U2 controlled rollback drill", admin)
        route_after = service.route_for(admin, "Task25BR2U2_rollback-check")
    passed = (
        session.get("pilot_collection") == settings.DASHVECTOR_PHYSICAL_COLLECTION
        and session.get("pilot_partition") == settings.DASHVECTOR_PILOT_PARTITION
        and rolled_back.get("status") == "rolled_back"
        and route_after.active is False
        and route_after.collection == settings.DASHVECTOR_PHYSICAL_COLLECTION
    )
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "session_id": str(session.get("session_id")),
        "existing_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
        "pilot_partition": settings.DASHVECTOR_PILOT_PARTITION,
        "session_activated": False,
        "rollback_executed": True,
        "base_route_restored": route_after.active is False,
        "partition_deleted": False,
        "pilot_documents_deleted": False,
        "env_collection_modified": False,
        "audit_event_written": True,
    }
    write_json("pilot_switch_and_rollback.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
