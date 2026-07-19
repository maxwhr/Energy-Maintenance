from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService


def test_grounded_vector_ids_are_stable_and_anchor_type_scoped() -> None:
    first = MaintenanceSemanticUnitService.anchor_vector_id("su-1", "ACTION")
    assert first == MaintenanceSemanticUnitService.anchor_vector_id("su-1", "ACTION")
    assert first != MaintenanceSemanticUnitService.anchor_vector_id("su-1", "SAFETY")
    assert first.startswith("suva_")

