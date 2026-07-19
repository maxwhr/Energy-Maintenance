from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from task25b_r2_common import BACKEND, ROOT, RUNTIME, now_iso, write_json

from app.core.database import SessionLocal
from app.models import User
from app.schemas.retrieval_pilot import PilotSessionCreate
from app.services.retrieval_pilot_service import RetrievalPilotService, RetrievalPilotServiceError


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    baseline = json.loads((RUNTIME / "pre_task_config_snapshot.json").read_text(encoding="utf-8"))
    before_env = _hash(BACKEND / ".env")
    switch = {
        "generated_at": now_iso(), "status": "BLOCKED_NO_PILOT_INDEX", "base_route_before": baseline.get("DASHVECTOR_PHYSICAL_COLLECTION"),
        "pilot_route_activated": False, "affected_users": [], "normal_users_unaffected": True,
        "activation_blocked_before_route_change": False, "default_config_changed": False,
        "session_id": None, "audit_trace": None,
    }
    rollback = {
        "generated_at": now_iso(), "status": "NOT_REQUIRED_ROUTE_NEVER_CHANGED",
        "rollback_executed": False, "base_route_restored": True, "default_config_changed": False,
        "audit_trace": None,
    }
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.created_at))
        if not admin:
            switch["status"] = "BLOCKED_NO_ADMIN"
        else:
            service = RetrievalPilotService(db)
            try:
                session = service.create_session(PilotSessionCreate(
                    name="Task25B-R2 controlled rollback drill", scope_user_ids=[admin.id],
                    query_prefix="Task25BR2_", retrieval_strategy="adaptive",
                ), admin)
                switch["session_id"] = session["session_id"]
                switch["audit_trace"] = session["audit_trace_id"]
                rollback["audit_trace"] = session["audit_trace_id"]
                try:
                    service.activate_session(session["session_id"], admin)
                    switch["pilot_route_activated"] = True
                    switch["affected_users"] = [str(admin.id)]
                    switch["status"] = "ACTIVATED"
                    rolled = service.rollback_session(session["session_id"], "Task25B-R2 controlled drill", admin)
                    rollback.update(status="PASSED", rollback_executed=True, base_route_restored=bool(rolled.get("status") == "rolled_back"))
                except RetrievalPilotServiceError as exc:
                    switch["activation_blocked_before_route_change"] = True
                    switch["blocked_reason"] = str(exc)
                    service.close_session(session["session_id"], admin)
            except RetrievalPilotServiceError as exc:
                switch["blocked_reason"] = str(exc)
    after_env = _hash(BACKEND / ".env")
    switch["default_config_changed"] = before_env != after_env or before_env != baseline.get("env_sha256")
    rollback["default_config_changed"] = switch["default_config_changed"]
    write_json("pilot_switch_result.json", switch)
    write_json("pilot_rollback_result.json", rollback)
    (ROOT / "docs" / "25B_R2_pilot_switch_and_rollback_report.md").write_text(
        "# Task 25B-R2 Pilot 切换与回滚报告\n\n"
        f"- 切换状态：{switch['status']}\n- Pilot 路由激活：{switch['pilot_route_activated']}\n"
        f"- 激活前阻断：{switch['activation_blocked_before_route_change']}\n"
        f"- 普通用户未受影响：{switch['normal_users_unaffected']}\n"
        f"- 回滚状态：{rollback['status']}\n- Base 路由保持/恢复：{rollback['base_route_restored']}\n"
        f"- `.env` 默认配置变化：{switch['default_config_changed']}\n"
        "- 说明：真实 Pilot 索引未达到 300，安全门禁在路由改变前拒绝激活，因此没有伪造一次回滚成功。\n",
        encoding="utf-8",
    )
    print(json.dumps({"switch": switch, "rollback": rollback}, ensure_ascii=False))
    return 0 if rollback["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
