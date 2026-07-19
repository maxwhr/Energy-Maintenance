from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.candidate_hydration_service import CandidateHydrationService, HydratedKeywordRow
from app.services.query_signal_extraction_service import QuerySignalExtractionService


def _row(chunk_id: str, content: str, section: str = "", title: str = "SUN2000 手册") -> HydratedKeywordRow:
    chunk = SimpleNamespace(id=chunk_id, chunk_index=0)
    document = SimpleNamespace(id=f"d-{chunk_id}", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    values = (content.casefold(), section.casefold(), title.casefold())
    return HydratedKeywordRow(chunk, document, *values, "\n".join(values))


def test_chinese_terms_retain_specific_phrases_without_space_tokenization() -> None:
    terms = QuerySignalExtractionService.retrieval_terms(
        "SUN2000 绝缘阻抗定位显示检测条件不满足时怎么逐串排查？"
    )

    assert "绝缘阻抗" in terms
    assert "检测条件不满足" in terms
    assert "排查" not in terms


def test_specific_chinese_evidence_outranks_generic_sun2000_content() -> None:
    rows = [
        _row("generic", "SUN2000 产品概述与设备说明。"),
        _row("direct", "绝缘阻抗故障位置定位检测条件不满足时，将光伏组串逐路接入。", "绝缘阻抗故障位置定位"),
    ]
    keywords = QuerySignalExtractionService.retrieval_terms(
        "SUN2000 绝缘阻抗定位显示检测条件不满足时怎么逐串排查？"
    )

    ranked = CandidateHydrationService.rank_keyword_candidates(rows, keywords=keywords, candidate_limit=2)

    assert [item[0].id for item in ranked] == ["direct"]


def test_explicit_alarm_code_outranks_year_and_generic_metadata() -> None:
    rows = [
        _row("year", "文档版本 2026，SUN2000 产品说明。"),
        _row("alarm", "告警ID 301 电网电压异常，应检查电网电压和交流断路器。", "告警参考"),
    ]
    keywords = QuerySignalExtractionService.retrieval_terms("SUN2000 告警码 301 电网电压异常如何排查？")

    ranked = CandidateHydrationService.rank_keyword_candidates(rows, keywords=keywords, candidate_limit=2)

    assert [item[0].id for item in ranked] == ["alarm"]
