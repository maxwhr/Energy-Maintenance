from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, or_, select, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import KnowledgeDocument  # noqa: E402


HUAWEI_ALIASES = {"huawei", "华为"}
SAFE_SOURCE_TYPES = {"vendor_official", "vendor_official_html", "knowledge_contribution", "user_upload"}


def _proposed_changes(document: KnowledgeDocument) -> dict:
    metadata = dict(document.metadata_json or {})
    manufacturer = str(document.manufacturer or "").strip().casefold()
    searchable = " ".join((
        document.title or "",
        document.model or "",
        str(metadata.get("product_family") or ""),
    ))
    searchable_lower = searchable.casefold()
    has_huawei_product = "sun2000" in searchable_lower or "fusionsolar" in searchable_lower
    if document.source_type not in SAFE_SOURCE_TYPES:
        return {}
    if manufacturer and manufacturer not in HUAWEI_ALIASES:
        return {}
    if not (manufacturer in HUAWEI_ALIASES or has_huawei_product):
        return {}

    changes: dict = {}
    if manufacturer in HUAWEI_ALIASES and document.manufacturer != "huawei":
        changes["manufacturer"] = "huawei"
    if not document.product_series:
        if "sun2000" in searchable_lower:
            changes["product_series"] = "SUN2000"
        elif "fusionsolar" in searchable_lower:
            changes["product_series"] = "FusionSolar"
    if document.device_type == "inverter":
        changes["device_type"] = "pv_inverter"
    if not metadata.get("product_family") and changes.get("product_series"):
        changes["metadata_json.product_family"] = changes["product_series"]
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotent Huawei scope metadata repair planner")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print proposals only (default)")
    mode.add_argument("--apply", action="store_true", help="Apply only additive/normalizing proposals")
    parser.add_argument(
        "--confirm-database",
        help="Required with --apply and must exactly match the connected database name",
    )
    args = parser.parse_args()
    database_name = str(engine.url.database or "")
    if args.apply and args.confirm_database != database_name:
        parser.error("--apply requires --confirm-database matching the connected database")

    with SessionLocal() as db:
        if not args.apply:
            db.execute(text("SET TRANSACTION READ ONLY"))
        candidates = list(db.scalars(
            select(KnowledgeDocument)
            .where(or_(
                func.lower(KnowledgeDocument.manufacturer).in_(HUAWEI_ALIASES),
                KnowledgeDocument.title.ilike("%SUN2000%"),
                KnowledgeDocument.title.ilike("%FusionSolar%"),
                KnowledgeDocument.model.ilike("%SUN2000%"),
            ))
            .order_by(KnowledgeDocument.id)
        ))
        proposals = []
        for document in candidates:
            changes = _proposed_changes(document)
            if not changes:
                continue
            proposals.append({
                "document_id": str(document.id),
                "title": document.title,
                "changes": changes,
            })
            if args.apply:
                for field, value in changes.items():
                    if field == "metadata_json.product_family":
                        metadata = dict(document.metadata_json or {})
                        metadata.setdefault("product_family", value)
                        document.metadata_json = metadata
                    else:
                        setattr(document, field, value)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps({
            "database_name": database_name,
            "mode": "apply" if args.apply else "dry-run",
            "proposal_count": len(proposals),
            "proposals": proposals,
            "review_status_changed": False,
            "source_type_changed": False,
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
