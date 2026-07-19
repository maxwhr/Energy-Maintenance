import inspect

from app.services.candidate_hydration_service import CandidateHydrationService


def test_candidate_hydration_has_one_execute_site_and_no_candidate_loop_query():
    source = inspect.getsource(CandidateHydrationService.load_scope_candidates)
    assert source.count("self.db.execute") == 1
    assert "for chunk, document in rows" in source
    assert "self.db.get" not in source
