from app.services.maintenance_feedback_loop_service import MaintenanceFeedbackLoopService


def test_provider_fallback_feedback_never_changes_production_state():
    result = MaintenanceFeedbackLoopService.build(
        initial_diagnosis={}, actual_result={"diagnosis_match_status": "UNDETERMINED"},
        execution_records=[], citations=[], user_feedback="provider fallback used",
    )
    assert "missing_citation" in result["missing_knowledge_signals"]
    assert result["production_effects"]["production_prompt_changed"] is False

