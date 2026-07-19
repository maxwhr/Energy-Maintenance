from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.candidate_hydration_service import CandidateHydrationService
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.retrieval_text_feature_service import RetrievalTextFeatureService
from app.services.rrf_fusion_service import QueryAwareCandidate


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("ＳＵＮ２０００－２０ＫＴＬ－Ｍ３", "sun2000-20ktl-m3"),
        ("SUN2000_20KTL_M3", "sun2000-20ktl-m3"),
        ("SUN2000 20KTL M3", "sun2000-20ktl-m3"),
        ("（SUN2000-20KTL-M3）", "(sun2000-20ktl-m3)"),
        ("告警，2063", "告警,2063"),
        ("SUN2000—20KTL—M3", "sun2000-20ktl-m3"),
        ("Sun2000-20Ktl-M3", "SUN2000-20KTL-M3"),
        ("  RS485   通信  ", "rs485 通信"),
    ],
)
def test_normalization_equivalence(left: str, right: str) -> None:
    normalize = RetrievalTextFeatureService.normalize_text
    compact = RetrievalTextFeatureService.compact_text
    assert compact(normalize(left)) == compact(normalize(right))


@pytest.mark.parametrize(
    ("expected", "candidate"),
    [
        ("SUN2000-5KTL-M0", "SUN2000-50KTL-M0"),
        ("SUN2000-20KTL-M0", "SUN2000-20KTL-M1"),
        ("SUN2000-20KTL-M1", "SUN2000-20KTL-M2"),
        ("SUN2000-20KTL-M2", "SUN2000-20KTL-M3"),
        ("SUN2000-33KTL-NH", "SUN2000-33KTL-M3"),
        ("SUN2000-196KTL-H0", "SUN2000-196KTL-H0++"),
        ("SUN2000-20KTL-M3", "SUN2000-20KTL-M0"),
        ("SUN2000-33KTL-NH", "SUN2000-33KTL-A"),
        ("SUN2000-8KTL-M2", "SUN2000-18KTL-M2"),
        ("SUN2000-30KTL-A", "SUN2000-30KTL-M3"),
    ],
)
def test_model_identifiers_do_not_partially_match(expected: str, candidate: str) -> None:
    candidate_models = RetrievalTextFeatureService.extract_model_identifiers(candidate)
    assert not RetrievalTextFeatureService.exact_model_match(expected, candidate_models)


@pytest.mark.parametrize(
    ("expected", "candidate"),
    [
        ("SUN2000-20KTL-M3", "SUN2000 20KTL M3"),
        ("SUN2000_33KTL_NH", "SUN2000-33KTL-NH"),
        ("（SUN2000-196KTL-H0++）", "SUN2000-196KTL-H0++"),
        ("SUN2000-30KTL-A", "sun2000 30ktl a"),
        ("SUN2000-8KTL-M2", "SUN2000_(8KTL-M2)"),
        ("SUN2000-33KTL", "SUN2000-33KTL-NH"),
        ("SUN2000-20KTL", "SUN2000-20KTL-M3"),
        ("SUN2000-5KTL-M0", "适用型号 SUN2000-5KTL-M0"),
    ],
)
def test_model_identifier_variants_match(expected: str, candidate: str) -> None:
    candidate_models = RetrievalTextFeatureService.extract_model_identifiers(candidate)
    assert RetrievalTextFeatureService.exact_model_match(expected, candidate_models)


@pytest.mark.parametrize("code", ["2001", "2011", "2051", "2063", "A1234"])
def test_alarm_codes_keep_exact_boundaries(code: str) -> None:
    features = RetrievalTextFeatureService.build(f"告警 {code} 处理说明")
    assert code in features.alarm_codes
    assert all(value == code or value not in code for value in features.alarm_codes)


@pytest.mark.parametrize(
    "term",
    ["RS485", "LVRT", "绝缘阻抗", "额定输出功率", "漏电动作电流"],
)
def test_parameter_terms_survive_normalization(term: str) -> None:
    features = RetrievalTextFeatureService.build(f"参数 {term} = 30kW / 1100V")
    assert term.casefold() in features.normalized
    assert "30kw" in features.tokens
    assert "1100v" in features.tokens


def _candidate(
    candidate_id: str,
    *,
    content: str,
    document_id: str = "doc-a",
    section: str = "section-a",
    score: float = 0.5,
    scope_ok: bool = True,
    exact_model: bool = False,
    support: set[str] | None = None,
) -> QueryAwareCandidate:
    item = QueryAwareCandidate(
        candidate_id=candidate_id,
        chunk_id=candidate_id,
        document_id=document_id,
        document_title=f"Manual {document_id}",
        content=content,
        section_title=section,
        page_number=1,
        chunk=SimpleNamespace(id=candidate_id, chunk_index=1, metadata_json={}),
        document=SimpleNamespace(id=document_id, title=f"Manual {document_id}", document_type="manual", metadata_json={}),
        source_channels={"SCOPED_KEYWORD"},
        source_query_types={"ORIGINAL"},
        source_chunk_ids=[candidate_id],
        source_locator={"section": section, "page_number": 1},
        scope_validation_passed=scope_ok,
        evidence_identity=f"section:{document_id}:{section}",
        evidence_equivalence_key=f"source_group:{candidate_id}",
        exact_model_match=exact_model,
        final_score=score,
        rerank_score=score,
    )
    item.requested_information_support = set(support or set())
    return item


def test_refinement_keeps_complementary_same_section_evidence() -> None:
    values = [
        _candidate("a", content="cause", section="same", support={"CAUSE"}),
        _candidate("b", content="action", section="same", support={"ACTION"}),
        _candidate("c", content="safety", section="same", support={"SAFETY"}),
    ]
    result = ResultSetRefinementService().refine_query_aware(values, requested_top_k=5)
    assert {item.chunk_id for item in result.surfaced} == {"a", "b", "c"}


def test_refinement_drops_scope_invalid_candidates() -> None:
    values = [
        _candidate("invalid", content="high score", score=1.0, scope_ok=False),
        _candidate("valid", content="valid evidence", score=0.5),
    ]
    result = ResultSetRefinementService().refine_query_aware(values, requested_top_k=5)
    assert [item.chunk_id for item in result.surfaced] == ["valid"]


def test_cache_invalidation_changes_generation_and_clears_entries() -> None:
    original_generation = CandidateHydrationService._cache_generation
    CandidateHydrationService._scope_cache[("scope",)] = (999999.0, object())
    CandidateHydrationService.invalidate_scope_cache()
    assert CandidateHydrationService._cache_generation == original_generation + 1
    assert CandidateHydrationService._scope_cache == {}


@pytest.mark.parametrize("revision_marker", ["a", "b", "c", "d", "e"])
def test_snapshot_revision_changes_with_corpus_revision(revision_marker: str) -> None:
    scope = SimpleNamespace(scope_id="scope-a")
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        (
            SimpleNamespace(id=f"chunk-{revision_marker}", updated_at=moment),
            SimpleNamespace(id="document", updated_at=moment),
        )
    ]
    revision = CandidateHydrationService._snapshot_revision(scope, rows)
    assert len(revision) == 64
    assert revision != CandidateHydrationService._snapshot_revision(scope, [])


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("告警 2063 处理步骤", "告警\n2063\t处理步骤"),
        ("SUN2000-20KTL-M3 技术数据", "SUN2000 - 20KTL - M3 技术数据"),
        ("额定输出功率 30kW", "额定输出功率：30kW"),
        ("RS485 通信参数", "RS485：通信参数"),
        ("绝缘阻抗检查", "绝缘阻抗  检查"),
        ("低电压穿越 LVRT", "低电压穿越（LVRT）"),
    ],
)
def test_content_fingerprint_is_stable_for_formatting_variants(left: str, right: str) -> None:
    left_features = RetrievalTextFeatureService.build(left)
    right_features = RetrievalTextFeatureService.build(right)
    assert left_features.content_fingerprint == right_features.content_fingerprint
