from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

from app.core.database import SessionLocal
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from task25b_r3_dev_common import ROOT, now_iso


OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def main() -> None:
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        count = RetrievalRepository(db).count_chunks_for_filters(device_type=None, scope=scope)
        frozen = False
        try:
            scope.scope_id = "mutated"  # type: ignore[misc]
        except (FrozenInstanceError, AttributeError):
            frozen = True
        checks = {
            "immutable": frozen, "scope_id": scope.scope_id == CHINESE_ENGINEERING_PILOT_SCOPE_ID,
            "document_count": len(scope.allowed_document_ids) == 16, "chunk_count": count == 1262,
            "chinese_only": scope.normalized_language == "zh-CN" and not scope.include_unknown_language,
            "pilot_only": scope.approved_for_pilot and scope.partition_name == "pilot_r2",
            "current_only": scope.current_version_only and not scope.include_superseded,
            "no_alternate": not scope.include_alternate_language, "no_test_fixture": not scope.include_test_fixture,
            "no_marketing": not scope.include_marketing,
            "collection": scope.collection_name == "energy_kn_te_v4_1024_v1",
        }
        payload = {"generated_at": now_iso(), "scope": scope.public_dict(), "eligible_chunks": count,
                   "checks": checks, "passed": all(checks.values())}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scope_contract.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED" if payload["passed"] else "FAILED", "documents": 16,
                      "chunks": count, "checks": checks}, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
