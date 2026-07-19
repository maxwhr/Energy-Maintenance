from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.candidate_hydration_service import CandidateHydrationService, HydratedKeywordRow


def row(chunk_id: str, title: str, section: str, content: str):
    chunk = SimpleNamespace(id=chunk_id, chunk_index=0)
    document = SimpleNamespace(id=f"d-{chunk_id}", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    return HydratedKeywordRow(chunk, document, content.casefold(), section.casefold(), title.casefold(), "\n".join((content, section, title)).casefold())


def test_batch_keyword_ranking_uses_precomputed_text_and_stable_order():
    rows = [row("b", "普通", "通信中断", "原因"), row("a", "通信中断", "普通", "原因")]
    ranked = CandidateHydrationService.rank_keyword_candidates(rows, keywords=["通信中断"], candidate_limit=2)
    assert [item[0].id for item in ranked] == ["b", "a"]

