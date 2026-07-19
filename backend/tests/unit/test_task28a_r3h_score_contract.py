from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType, SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories.retrieval_repository import KeywordCandidateHit, RetrievalRepository
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest, QueryAwareSearchResponse
from app.schemas.retrieval_scope import RetrievalScope
from app.services.candidate_hydration_service import (
    CandidateHydrationResult,
    CandidateHydrationService,
    HydratedKeywordRow,
)
from app.services.deterministic_evidence_rerank_service import (
    DeterministicEvidenceRerankService,
)
from app.services.multi_query_retrieval_service import MultiQueryRetrievalService
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.rrf_fusion_service import QueryAwareCandidate, RRFFusionService
from tests.minimax_test_helpers import candidate, understanding


def keyword_row(
    chunk_id: str,
    *,
    title: str = "华为 SUN2000 官方手册",
    section: str = "故障处理",
    content: str = "逆变器故障排查",
    updated_at: datetime | None = None,
) -> HydratedKeywordRow:
    stamp = updated_at or datetime(2026, 7, 1, tzinfo=timezone.utc)
    chunk = SimpleNamespace(
        id=chunk_id,
        chunk_index=0,
        content=content,
        section_title=section,
        page_number=2,
        metadata_json={},
        updated_at=stamp,
    )
    document = SimpleNamespace(
        id=f"doc-{chunk_id}",
        title=title,
        model="SUN2000",
        summary="",
        source="official",
        metadata_json={},
        created_at=stamp,
        updated_at=stamp,
        document_type="manual",
    )
    return HydratedKeywordRow(
        chunk=chunk,
        document=document,
        content=content.casefold(),
        section=section.casefold(),
        title=title.casefold(),
        search_blob="\n".join((content, section, title)).casefold(),
    )


def scope_for(document_id) -> RetrievalScope:
    return RetrievalScope(
        scope_id="huawei_sun2000_competition_v1",
        corpus_type="competition_delivery",
        normalized_language="zh-CN",
        allowed_document_ids=(document_id,),
        required_document_status="approved",
        required_chunk_status="active",
        required_approval_mode=("approved",),
        approved_for_pilot=False,
        current_version_only=True,
        collection_name="unit-test",
        partition_name="unit-test",
        manufacturer="huawei",
        product_families=("SUN2000", "FusionSolar"),
        device_type="pv_inverter",
    )


def scored_candidate(
    candidate_id: str,
    *,
    relevance: float,
    query_type: str = "ORIGINAL",
    channel: str = "SCOPED_KEYWORD",
    evidence_key: str | None = None,
    exact_model: bool = False,
    exact_alarm: bool = False,
) -> QueryAwareCandidate:
    item = QueryAwareCandidate(
        candidate_id=candidate_id,
        chunk_id=candidate_id,
        document_id=f"doc-{candidate_id}",
        document_title=f"官方文档 {candidate_id}",
        section_title="直接证据",
        content="华为 SUN2000 检修直接证据",
        source_channels={channel},
        source_query_types={query_type},
        normalized_relevance_score=relevance,
        raw_relevance_score=relevance * 100,
        repository_rank=1,
        exact_model_match=exact_model,
        exact_alarm_match=exact_alarm,
        source_chunk_ids=[candidate_id],
        source_locator={"page_number": 1, "section": "直接证据"},
        scope_validation_passed=True,
    )
    item.evidence_identity = evidence_key or candidate_id
    item.evidence_equivalence_key = evidence_key or candidate_id
    return item


def official_document(**updates):
    values = {
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "source_type": "vendor_official",
        "title": "SUN2000 用户手册",
        "model": "SUN2000",
        "status": "active",
        "parse_status": "parsed",
        "review_status": "approved",
        "metadata_json": {"normalized_language": "zh-CN"},
    }
    values.update(updates)
    return SimpleNamespace(**values)


# 1. Repository 原始分数可以进入 Candidate。
def test_01_repository_score_enters_candidate() -> None:
    row = keyword_row("score-source", content="通信断链保护时间参数")
    hit = KeywordCandidateHit(
        chunk=row.chunk,
        document=row.document,
        raw_relevance_score=42.0,
        normalized_relevance_score=0.84,
        repository_rank=3,
        matched_fields=("content",),
        matched_tokens=("通信断链保护时间",),
        score_source="scope_snapshot_text_features",
        score_breakdown={"raw_relevance_score": 42.0},
    )
    item = MultiQueryRetrievalService._candidate(
        row.chunk,
        row.document,
        "SCOPED_KEYWORD",
        "ORIGINAL",
        hit.normalized_relevance_score,
        understanding("通信断链保护时间是多少"),
        scope_for(row.document.id),
        keyword_hit=hit,
    )
    assert item.raw_relevance_score == 42.0
    assert item.normalized_relevance_score == 0.84
    assert item.repository_rank == 3


# 2. `_keyword()` 不再无条件用 `1/rank` 覆盖分数。
def test_02_keyword_keeps_normalized_score_instead_of_rank_reciprocal() -> None:
    rows = (
        keyword_row("strong", section="通信断链保护时间", content="通信断链保护时间参数说明"),
        keyword_row("weak", section="通信", content="一般通信参数"),
    )
    scope = replace(
        scope_for(rows[0].document.id),
        allowed_document_ids=tuple(row.document.id for row in rows),
    )
    values = MultiQueryRetrievalService(allow_real_api=False)._keyword(
        "SCOPED_KEYWORD",
        "通信断链保护时间参数",
        "ORIGINAL",
        understanding("通信断链保护时间参数"),
        scope,
        2,
        hydrated_keyword_rows=rows,
    )
    assert values[1].normalized_relevance_score != pytest.approx(0.5)
    assert values[0].normalized_relevance_score > values[1].normalized_relevance_score


# 3. 强匹配与弱匹配分数差距被保留。
def test_03_strong_and_weak_keyword_scores_remain_distinct() -> None:
    hits = CandidateHydrationService.rank_keyword_candidate_hits(
        (
            keyword_row("strong-gap", section="低电压穿越无功支撑", content="低电压穿越无功支撑参数"),
            keyword_row("weak-gap", section="电网", content="一般电网参数"),
        ),
        keywords=["低电压穿越", "无功支撑", "参数"],
        candidate_limit=2,
    )
    assert hits[0].raw_relevance_score > hits[1].raw_relevance_score
    assert hits[0].normalized_relevance_score > hits[1].normalized_relevance_score


# 4. Uniform score 有稳定 fallback。
def test_04_uniform_zero_repository_scores_have_stable_rank_fallback() -> None:
    first = keyword_row("fallback-a")
    second = keyword_row("fallback-b")
    fake_db = SimpleNamespace(
        execute=lambda _statement: FakeRowsResult(
            [(first.chunk, first.document, 0), (second.chunk, second.document, 0)]
        )
    )
    hits = RetrievalRepository(fake_db).list_scored_knowledge_candidates(keywords=["未计分词"], candidate_limit=2)
    assert [hit.normalized_relevance_score for hit in hits] == [1.0, 0.5]
    assert all(hit.score_fallback_used for hit in hits)


# 5. 正式关键词路径 fallback 比例为 0。
def test_05_feature_scored_keyword_path_uses_no_fallback() -> None:
    hits = CandidateHydrationService.rank_keyword_candidate_hits(
        (keyword_row("normal-path", content="SUN2000-50KTL-M3 绝缘阻抗排查"),),
        keywords=["SUN2000-50KTL-M3", "绝缘阻抗"],
        candidate_limit=5,
    )
    assert hits and sum(hit.score_fallback_used for hit in hits) / len(hits) == 0.0


# 6. Score breakdown 可审计。
def test_06_score_breakdown_is_auditable() -> None:
    hit = CandidateHydrationService.rank_keyword_candidate_hits(
        (keyword_row("audit", section="Error 225", content="Error 225 告警处理"),),
        keywords=["Error 225", "告警处理"],
        candidate_limit=1,
    )[0]
    assert hit.score_breakdown["raw_relevance_score"] == hit.raw_relevance_score
    assert "maximum_relevance_score" in hit.score_breakdown
    assert hit.score_source == "scope_snapshot_text_features"


# 7. Duplicate Variant 不重复主投票。
def test_07_duplicate_variant_does_not_repeat_primary_vote() -> None:
    single = RRFFusionService()
    single_result = single.fuse({"SCOPED_KEYWORD:ORIGINAL:q0": [scored_candidate("single", relevance=0.8, evidence_key="e")]})
    duplicate = RRFFusionService()
    duplicate_result = duplicate.fuse({
        "SCOPED_KEYWORD:ORIGINAL:q0": [scored_candidate("dup-a", relevance=0.8, evidence_key="e")],
        "SCOPED_KEYWORD:ORIGINAL:q1": [scored_candidate("dup-b", relevance=0.8, evidence_key="e")],
    })
    assert duplicate_result[0].rrf_score == single_result[0].rrf_score
    assert duplicate.last_diagnostics["duplicate_votes_removed"] == 1


# 8. 同 Query Family 只保留最高主贡献。
def test_08_same_query_family_keeps_highest_channel_vote() -> None:
    fusion = RRFFusionService()
    fusion.fuse({
        "SCOPED_KEYWORD:CAUSE:q0": [scored_candidate("family-low", relevance=0.2, query_type="CAUSE", evidence_key="family")],
        "SCOPED_KEYWORD:CAUSE:q1": [scored_candidate("family-high", relevance=0.9, query_type="CAUSE", evidence_key="family")],
    })
    vote = fusion.last_diagnostics["vote_breakdown"]["family-low"]["SCOPED_KEYWORD"]
    assert vote["query_family"] == "CAUSE"
    assert vote["normalized_relevance_contribution"] > 0.0


# 9. Generic Variant 不能淹没 Original 精确命中。
def test_09_generic_variants_cannot_overwhelm_original_exact_hit() -> None:
    rankings = {
        "SCOPED_KEYWORD:ORIGINAL:q0": [scored_candidate("exact", relevance=1.0, exact_model=True)],
        **{
            f"SCOPED_KEYWORD:GENERAL:q{index}": [scored_candidate(f"generic-{index}", relevance=0.25, evidence_key="generic")]
            for index in range(4)
        },
    }
    output = RRFFusionService().fuse(rankings, query_weights={"ORIGINAL": 1.0, "GENERAL": 0.4})
    assert output[0].candidate_id == "exact"


# 10. Variant 数量变化不会无限改变分数。
@pytest.mark.parametrize("variant_count", [2, 3, 4, 5])
def test_10_variant_count_has_bounded_same_channel_contribution(variant_count: int) -> None:
    rankings = {
        f"SCOPED_KEYWORD:GENERAL:q{index}": [scored_candidate(f"v-{index}", relevance=0.4, evidence_key="same")]
        for index in range(variant_count)
    }
    result = RRFFusionService().fuse(rankings)
    assert result[0].rrf_score == pytest.approx(1 / 61 + 0.012 * 0.4)


# 11. 同一物理 Channel 投票受限。
def test_11_physical_channel_vote_is_capped() -> None:
    fusion = RRFFusionService()
    fusion.fuse({
        "SCOPED_KEYWORD:ORIGINAL:q0": [scored_candidate("cap-a", relevance=0.6, evidence_key="cap")],
        "SCOPED_KEYWORD:SAFETY:q1": [scored_candidate("cap-b", relevance=0.7, evidence_key="cap")],
    })
    assert fusion.last_diagnostics["channel_vote_cap"] == 1
    assert len(fusion.last_diagnostics["vote_breakdown"]["cap-a"]) == 1


# 12. Original Query contribution 可追踪。
def test_12_original_query_contribution_is_traceable() -> None:
    fusion = RRFFusionService()
    fusion.fuse({"SCOPED_KEYWORD:ORIGINAL:q0": [scored_candidate("trace-original", relevance=0.9)]})
    vote = fusion.last_diagnostics["vote_breakdown"]["trace-original"]["SCOPED_KEYWORD"]
    assert vote["query_family"] == "ORIGINAL"
    assert vote["rrf_contribution"] > 0


# 13. 5KTL 不等于 50KTL。
def test_13_model_5ktl_does_not_match_50ktl() -> None:
    assert not MultiQueryRetrievalService._contains_exact_identifier("SUN2000-50KTL-M3", "SUN2000-5KTL-M0")


# 14. M0 不等于 M1/M2/M3。
@pytest.mark.parametrize("other", ["M1", "M2", "M3"])
def test_14_model_m0_is_distinct_from_other_generations(other: str) -> None:
    assert not MultiQueryRetrievalService._contains_exact_identifier(f"SUN2000-50KTL-{other}", "SUN2000-50KTL-M0")


# 15. NH 不等于 M3。
def test_15_model_nh_is_distinct_from_m3() -> None:
    assert not MultiQueryRetrievalService._contains_exact_identifier("SUN2000-50KTL-M3", "SUN2000-50KTL-NH")


# 16. H0 不等于 H0++。
def test_16_model_h0_is_distinct_from_h0_plus_plus() -> None:
    assert not MultiQueryRetrievalService._contains_exact_identifier("SUN2000-100KTL-H0++", "SUN2000-100KTL-H0")
    assert MultiQueryRetrievalService._contains_exact_identifier("SUN2000-100KTL-H0++", "SUN2000-100KTL-H0++")


# 17. 告警代码精确区分。
def test_17_alarm_codes_use_numeric_boundaries() -> None:
    assert MultiQueryRetrievalService._contains_exact_term("Error 225 绝缘告警", "225")
    assert not MultiQueryRetrievalService._contains_exact_term("Error 225 绝缘告警", "22")


# 18. 参数名称精确区分。
def test_18_exact_parameter_phrase_beats_generic_parameter_text() -> None:
    hits = CandidateHydrationService.rank_keyword_candidate_hits(
        (
            keyword_row("parameter-exact", section="通信断链保护时间参数", content="通信断链保护时间参数配置范围"),
            keyword_row("parameter-generic", section="通信参数", content="一般参数配置"),
        ),
        keywords=["通信断链保护时间参数"],
        candidate_limit=2,
    )
    assert hits[0].chunk.id == "parameter-exact"
    assert hits[0].exact_body_phrase_matches


# 19. 数值和单位绑定。
def test_19_numeric_value_and_unit_proximity_is_preserved() -> None:
    near, far = DeterministicEvidenceRerankService.phrase_proximity_profiles(
        ["20", "ms", "保护时间"],
        ["保护时间设置为 20 ms", "保护时间" + "普通说明" * 90 + "20 ms"],
    )
    assert near["score"] > far["score"]


# 20. 稀有复合短语保留。
def test_20_rare_compound_phrase_has_stronger_lexical_support() -> None:
    terms = ["低电压穿越无功支撑", "电网"]
    exact = DeterministicEvidenceRerankService.query_lexical_support(terms, "低电压穿越无功支撑功能")
    generic = DeterministicEvidenceRerankService.query_lexical_support(terms, "电网异常说明")
    assert exact > generic


def rerank_understanding(query: str, **updates):
    return understanding(query).model_copy(update=updates)


def anchored_candidate(label: str, content: str, *, rrf: float = 0.2, relevance: float = 0.9, **updates):
    item = candidate(label, content=content, rrf=rrf, **updates)
    item.normalized_relevance_score = relevance
    item.raw_relevance_score = relevance * 100
    return item


# 21. 精确型号直接证据不被无型号泛化文本压低。
def test_21_exact_model_direct_evidence_is_monotonic() -> None:
    exact = anchored_candidate("exact-model", "SUN2000-50KTL-M3 故障处理步骤", exact_model=True)
    generic = anchored_candidate("generic-model", "逆变器一般故障处理步骤", rrf=0.9, relevance=0.2)
    result = DeterministicEvidenceRerankService().rerank(
        [generic, exact],
        understanding=rerank_understanding(
            "SUN2000-50KTL-M3 故障处理步骤",
            device_models=["SUN2000-50KTL-M3"],
            requested_information=["PROCEDURE"],
        ),
    )
    assert result.candidates[0].candidate_id == "exact-model"


# 22. 精确告警码证据不被相邻告警压低。
def test_22_exact_alarm_direct_evidence_is_monotonic() -> None:
    exact = anchored_candidate("alarm-225", "Error 225 绝缘阻抗告警原因与处理", exact_alarm=True)
    adjacent = anchored_candidate("alarm-224", "Error 224 一般电网告警", rrf=0.9, relevance=0.2)
    result = DeterministicEvidenceRerankService().rerank(
        [adjacent, exact],
        understanding=rerank_understanding(
            "Error 225 的原因和处理",
            alarm_codes=["225"],
            requested_information=["CAUSE", "ACTION"],
        ),
    )
    assert result.candidates[0].candidate_id == "alarm-225"


# 23. 精确参数行不被一般参数表压低。
def test_23_exact_parameter_line_is_monotonic() -> None:
    exact = anchored_candidate("parameter-line", "通信断链保护时间参数为 20 ms")
    exact.exact_body_phrase_matches.add("通信断链保护时间")
    generic = anchored_candidate("parameter-table", "一般通信参数表和设置说明", rrf=0.9, relevance=0.3)
    result = DeterministicEvidenceRerankService().rerank(
        [generic, exact],
        understanding=rerank_understanding(
            "通信断链保护时间参数",
            requested_information=["CONFIGURATION"],
            components=["通信断链保护时间"],
        ),
    )
    assert result.candidates[0].candidate_id == "parameter-line"


# 24. 具体禁止动作不被一般安全文本压低。
def test_24_specific_prohibition_is_monotonic() -> None:
    exact = anchored_candidate("specific-safety", "严禁带电拆装线缆，必须先断电并验电")
    exact.exact_body_phrase_matches.add("严禁带电拆装线缆")
    generic = anchored_candidate("generic-safety", "请遵守一般安全规定", rrf=0.9, relevance=0.2)
    result = DeterministicEvidenceRerankService().rerank(
        [generic, exact],
        understanding=rerank_understanding(
            "严禁带电拆装线缆的安全要求",
            requested_information=["SAFETY"],
        ),
    )
    assert result.candidates[0].candidate_id == "specific-safety"


# 25. 存在冲突时允许精确候选降级。
def test_25_conflict_disables_direct_anchor_protection() -> None:
    item = anchored_candidate("conflict", "SUN2000-50KTL-M3 参数", exact_model=True)
    strength = DeterministicEvidenceRerankService._direct_anchor_strength(
        item,
        understanding=rerank_understanding("SUN2000-50KTL-M3 参数", device_models=["SUN2000-50KTL-M3"]),
        query_lexical_support=1.0,
        phrase_proximity_support=1.0,
        citation_quality=1.0,
        conflict_penalty=0.2,
    )
    assert strength == 0


# 26. 严格超集证据允许超越。
def test_26_strict_superset_evidence_can_overtake_partial_support() -> None:
    partial = anchored_candidate("partial", "Error 225 告警原因", exact_alarm=True, rrf=0.5)
    complete = anchored_candidate("complete", "Error 225 告警原因，检查绝缘阻抗并完成处理", exact_alarm=True, rrf=0.5)
    partial.section_title = "告警原因"
    complete.section_title = "告警原因与处理"
    result = DeterministicEvidenceRerankService().rerank(
        [partial, complete],
        understanding=rerank_understanding(
            "Error 225 的原因和处理步骤",
            alarm_codes=["225"],
            requested_information=["CAUSE", "ACTION"],
        ),
    )
    assert result.candidates[0].candidate_id == "complete"


# 27. 每次保护或覆盖都有原因。
def test_27_monotonic_protection_records_reason() -> None:
    item = anchored_candidate("reason", "SUN2000-50KTL-M3 直接处理", exact_model=True)
    result = DeterministicEvidenceRerankService().rerank(
        [item],
        understanding=rerank_understanding("SUN2000-50KTL-M3 处理", device_models=["SUN2000-50KTL-M3"]),
    )
    details = result.diagnostics["score_breakdown"]["reason"]
    assert details["monotonic_anchor_strength"] > 0
    assert details["monotonic_override_reason"].startswith("MONOTONIC_DIRECT_ANCHOR_LEVEL_")


# 28. 通用“参数”不等于指定参数。
def test_28_generic_parameter_does_not_equal_named_parameter() -> None:
    query = rerank_understanding(
        "通信断链保护时间参数如何配置",
        requested_information=["CONFIGURATION"],
        components=["通信断链保护时间"],
    )
    generic = anchored_candidate("generic-config", "一般参数配置说明")
    exact = anchored_candidate("exact-config", "通信断链保护时间参数配置说明")
    generic_score = DeterministicEvidenceRerankService._contextual_intent_evidence_score(generic, query)
    exact_score = DeterministicEvidenceRerankService._contextual_intent_evidence_score(exact, query)
    assert exact_score > generic_score


# 29. 通用“电网异常”不等于 LVRT。
def test_29_generic_grid_abnormality_does_not_equal_lvrt() -> None:
    exact, generic = DeterministicEvidenceRerankService.phrase_proximity_profiles(
        ["低电压穿越", "无功支撑"],
        ["低电压穿越期间提供无功支撑", "一般电网异常和电压告警"],
    )
    assert exact["score"] > generic["score"]


# 30. 通用“线缆安全”不等于禁止带电拆装。
def test_30_generic_cable_safety_does_not_equal_live_disassembly_prohibition() -> None:
    query = rerank_understanding("严禁带电拆装线缆", requested_information=["SAFETY"])
    exact = DeterministicEvidenceRerankService._safety_intent_score(
        query.original_query,
        "严禁带电拆装线缆，先断开电源并使用绝缘手套",
    )
    generic = DeterministicEvidenceRerankService._safety_intent_score(
        query.original_query,
        "线缆应整齐布置并遵守安全要求",
    )
    assert exact > generic


# 31. 原因词不等于处理步骤。
def test_31_cause_words_do_not_imply_action_steps() -> None:
    support = DeterministicEvidenceRerankService.requested_information_support(
        "告警原因可能是绝缘阻抗偏低",
        ["CAUSE", "ACTION"],
    )
    assert "CAUSE" in support
    assert "ACTION" not in support


# 32. 跨段拼接不构成完整直接支持。
def test_32_cross_paragraph_stitching_has_lower_proximity() -> None:
    joined, split = DeterministicEvidenceRerankService.phrase_proximity_profiles(
        ["通信断链保护时间", "20 ms"],
        ["通信断链保护时间为 20 ms", "通信断链保护时间" + "背景说明" * 100 + "20 ms"],
    )
    assert joined["score"] > split["score"]


# 33. 句内/邻近完整支持获得更高分。
def test_33_sentence_local_support_scores_higher() -> None:
    profiles = DeterministicEvidenceRerankService.phrase_proximity_profiles(
        ["绝缘阻抗", "Error 225", "检查"],
        ["Error 225 时检查绝缘阻抗", "Error 225" + "一般内容" * 90 + "检查绝缘阻抗"],
    )
    assert profiles[0]["score"] > profiles[1]["score"]


# 34. Sungrow 不进入 Huawei Scope。
def test_34_sungrow_document_is_outside_huawei_scope() -> None:
    assert not RetrievalScopeService.is_huawei_sun2000_document_eligible(
        official_document(manufacturer="sungrow", product_series="SG")
    )


# 35. Pending 不可召回。
def test_35_pending_document_is_not_eligible() -> None:
    assert not RetrievalScopeService.is_huawei_sun2000_document_eligible(
        official_document(review_status="pending_review")
    )


# 36. Archived 不可召回。
def test_36_archived_document_is_not_eligible() -> None:
    assert not RetrievalScopeService.is_huawei_sun2000_document_eligible(
        official_document(status="archived")
    )


# 37. Deleted 不可召回。
def test_37_deleted_document_is_not_eligible() -> None:
    assert not RetrievalScopeService.is_huawei_sun2000_document_eligible(
        official_document(status="deleted")
    )


# 38. 用户内容不替代官方证据。
def test_38_unreviewed_user_content_is_not_official_evidence() -> None:
    user_document = official_document(source_type="user_upload")
    assert not RetrievalScopeService.is_huawei_sun2000_document_eligible(user_document)
    user_document.metadata_json["human_expert_approved"] = True
    assert RetrievalScopeService.is_huawei_sun2000_document_eligible(user_document)


# 39. Empty Chunk 不可引用。
def test_39_empty_chunk_has_no_citation_quality() -> None:
    item = QueryAwareCandidate(
        candidate_id="empty",
        chunk_id="empty",
        document_id="doc-empty",
        document_title="空片段",
        content="",
        scope_validation_passed=True,
    )
    assert DeterministicEvidenceRerankService._citation_quality(item, None) == 0.0


# 40. Persist false 零写入。
def test_40_persist_false_skips_qa_repository_and_commit() -> None:
    service = QueryAwareRetrievalService.__new__(QueryAwareRetrievalService)
    service.db = SimpleNamespace(commit=lambda: pytest.fail("commit must not be called"))
    service.qa_repository = SimpleNamespace(create_qa_record=lambda _record: pytest.fail("write must not be called"))
    response = QueryAwareSearchResponse(
        request_id="preview",
        original_query="预览查询",
        normalized_query="预览查询",
        canonical_question="预览查询",
        primary_intent="GENERAL",
        confidence_status="LOW",
    )
    service._persist_qa_record(
        response,
        QueryAwareSearchRequest(query="预览查询", persist_result=False, enable_llm=False, allow_real_api=False),
        SimpleNamespace(),
    )
    assert response.persistence_status == "skipped_preview"


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeScopeDb:
    def __init__(self, rows):
        self.rows = rows
        self.execute_count = 0

    def execute(self, _statement):
        self.execute_count += 1
        return FakeRowsResult(self.rows)


def cache_scope(document_id) -> RetrievalScope:
    return replace(scope_for(document_id), scope_id=f"cache-{document_id}")


# 41. 保持 R3G 每次 Miss 最多一次 Scope SQL。
def test_41_scope_cache_miss_uses_one_sql(monkeypatch) -> None:
    CandidateHydrationService.invalidate_scope_cache()
    row = keyword_row("cache-miss")
    db = FakeScopeDb([(row.chunk, row.document)])
    monkeypatch.setattr("app.services.candidate_hydration_service.get_settings", lambda: SimpleNamespace(RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS=60))
    result = CandidateHydrationService(db).load_scope_candidates(cache_scope(row.document.id))
    assert result.sql_count == 1
    assert db.execute_count == 1


# 42. Cache hit 与 miss 排序完全一致。
def test_42_cache_hit_and_miss_ranking_are_identical(monkeypatch) -> None:
    CandidateHydrationService.invalidate_scope_cache()
    rows = [keyword_row("cache-a", section="Error 225"), keyword_row("cache-b", section="一般告警")]
    db = FakeScopeDb([(item.chunk, item.document) for item in rows])
    monkeypatch.setattr("app.services.candidate_hydration_service.get_settings", lambda: SimpleNamespace(RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS=60))
    scope = replace(
        cache_scope(rows[0].document.id),
        allowed_document_ids=tuple(item.document.id for item in rows),
    )
    service = CandidateHydrationService(db)
    miss = service.load_scope_candidates(scope)
    hit = service.load_scope_candidates(scope)
    miss_ids = [item.chunk.id for item in service.rank_keyword_candidate_hits(miss.keyword_rows, keywords=["Error 225"], candidate_limit=2)]
    hit_ids = [item.chunk.id for item in service.rank_keyword_candidate_hits(hit.keyword_rows, keywords=["Error 225"], candidate_limit=2)]
    assert hit.cache_hit is True and hit.sql_count == 0
    assert miss_ids == hit_ids


# 43. Corpus revision 变化后失效。
def test_43_corpus_invalidation_forces_new_snapshot(monkeypatch) -> None:
    CandidateHydrationService.invalidate_scope_cache()
    row = keyword_row("cache-revision")
    db = FakeScopeDb([(row.chunk, row.document)])
    monkeypatch.setattr("app.services.candidate_hydration_service.get_settings", lambda: SimpleNamespace(RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS=60))
    service = CandidateHydrationService(db)
    scope = cache_scope(row.document.id)
    first = service.load_scope_candidates(scope)
    CandidateHydrationService.invalidate_scope_cache()
    second = service.load_scope_candidates(scope)
    assert first.cache_hit is False and second.cache_hit is False
    assert db.execute_count == 2


# 44. Review 变化后失效。
def test_44_review_invalidation_clears_cached_snapshot(monkeypatch) -> None:
    CandidateHydrationService.invalidate_scope_cache()
    row = keyword_row("cache-review")
    db = FakeScopeDb([(row.chunk, row.document)])
    monkeypatch.setattr("app.services.candidate_hydration_service.get_settings", lambda: SimpleNamespace(RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS=60))
    service = CandidateHydrationService(db)
    scope = cache_scope(row.document.id)
    service.load_scope_candidates(scope)
    CandidateHydrationService.invalidate_scope_cache()
    refreshed = service.load_scope_candidates(scope)
    assert refreshed.cache_hit is False
    assert db.execute_count == 2


# 45. Snapshot 不可变。
def test_45_snapshot_mappings_are_immutable() -> None:
    result = CandidateHydrationResult(
        rows=(),
        keyword_rows=(),
        chunks=MappingProxyType({"chunk": SimpleNamespace(id="chunk")}),
        documents=MappingProxyType({"document": SimpleNamespace(id="document")}),
        elapsed_ms=0.0,
        sql_count=0,
    )
    with pytest.raises(TypeError):
        result.chunks["other"] = SimpleNamespace(id="other")
