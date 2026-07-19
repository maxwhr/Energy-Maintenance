from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import MaintenanceSemanticAnchor


def test_r5_semantic_index_is_active_source_grounded_and_expert_false() -> None:
    with SessionLocal() as db:
        rows = list(db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
            MaintenanceSemanticAnchor.index_status == "active",
        )))
        assert len(rows) == 2508
        assert len({row.vector_id for row in rows}) == 2508
        assert all(((row.semantic_fields or {}).get("semantic_unit") or {}).get("source_grounded") for row in rows)
        assert not any(((row.semantic_fields or {}).get("semantic_unit") or {}).get("expert_verified") for row in rows)
        assert db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == "pilot_r4_grounded",
            MaintenanceSemanticAnchor.index_status == "active",
        )) == 1289
