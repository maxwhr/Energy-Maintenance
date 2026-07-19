from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.candidate_hydration_service import CandidateHydrationService, HydratedKeywordRow


def test_batch_rank_matches_sql_contract_order_for_equal_candidates():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for chunk_id, chunk_index in (("a", 2), ("b", 1)):
        chunk = SimpleNamespace(id=chunk_id, chunk_index=chunk_index)
        document = SimpleNamespace(id="d", created_at=created)
        rows.append(HydratedKeywordRow(chunk, document, "通信中断", "告警", "手册", "通信中断\n告警\n手册"))
    ranked = CandidateHydrationService.rank_keyword_candidates(rows, keywords=["通信中断"], candidate_limit=2)
    assert [chunk.id for chunk, _document in ranked] == ["b", "a"]
