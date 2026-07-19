from app.services.maintenance_feedback_loop_service import MaintenanceFeedbackLoopService


def test_feedback_is_analysis_only_and_records_mismatch_signal():
    result = MaintenanceFeedbackLoopService.build(
        initial_diagnosis={"possible_faults": ["communication_interruption"]},
        actual_result={"diagnosis_match_status": "MISMATCHED", "actual_fault_cause": "connector"},
        execution_records=[{"record_type": "NEW_FINDING"}],
        citations=[{"chunk_id": "chunk-1"}],
        user_feedback="resolved",
    )
    assert "diagnosis_mismatch" in result["missing_knowledge_signals"]
    assert not any(result["production_effects"].values())

