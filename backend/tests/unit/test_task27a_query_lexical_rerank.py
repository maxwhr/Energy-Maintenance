from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.retrieval import RetrievedChunk, RetrievalQueryRequest
from app.services.answer_generation_service import AnswerGenerationService
from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from tests.minimax_test_helpers import candidate, understanding


def _retrieved(content: str, score: float = 1.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="华为 SUN2000 官方手册",
        chunk_index=0,
        section_title="故障处理",
        content=content,
        score=score,
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        document_type="manual",
        source="official",
        created_at=datetime.now(timezone.utc),
    )


def test_direct_chinese_phrase_outranks_generic_rrf_candidate() -> None:
    query = understanding("SUN2000 通信中断后自动关机的判定时间在哪里设置？")
    generic = candidate(
        "generic",
        content="SUN2000 通信异常时可以检查网络并重新设置连接参数。",
        rrf=0.90,
        exact_model=True,
    )
    direct = candidate(
        "direct",
        content="通信中断后自动关机的判定时间可在通信参数页面设置。",
        rrf=0.65,
        exact_model=True,
    )

    result = DeterministicEvidenceRerankService().rerank(
        [generic, direct],
        understanding=query,
    )

    assert result.candidates[0].candidate_id == "direct", result.diagnostics["score_breakdown"]
    assert result.diagnostics["score_breakdown"]["direct"]["query_lexical_support"] > result.diagnostics["score_breakdown"]["generic"]["query_lexical_support"]
    assert "EXACT_ENTITY_VALID_CITATION_PROTECTED" not in result.diagnostics["score_breakdown"]["direct"]["reason_codes"]


def test_rare_identifier_and_compound_phrase_receive_auditable_bonus() -> None:
    query = understanding("FusionSolar 中 SUN2000 的 RS485-2 通信断链保护时间如何配置？")
    query.requested_information = ["PROCEDURE", "CONFIGURATION"]
    generic = candidate(
        "generic",
        content="通信参数页面可以设置通信断链保护时间，并按操作步骤保存。",
        rrf=0.78,
        exact_model=True,
    )
    direct = candidate(
        "direct",
        content="在 RS485-2 参数中设置通信断链保护时间-2(s)，保存后确认参数生效。",
        rrf=0.68,
        exact_model=True,
    )

    result = DeterministicEvidenceRerankService().rerank(
        [generic, direct],
        understanding=query,
    )
    direct_breakdown = result.diagnostics["score_breakdown"]["direct"]
    generic_breakdown = result.diagnostics["score_breakdown"]["generic"]
    assert direct_breakdown["phrase_proximity_support"] > generic_breakdown["phrase_proximity_support"]
    assert any("rs485-2" in term for term in direct_breakdown["matched_phrase_anchor_terms"])


def test_phrase_proximity_profiles_do_not_need_benchmark_labels() -> None:
    profiles = DeterministicEvidenceRerankService.phrase_proximity_profiles(
        ["mppt多峰扫描", "组串遮挡", "为什么", "sun2000"],
        [
            "启用 MPPT 多峰扫描可在组串遮挡时执行全局扫描。",
            "SUN2000 支持常规 MPPT 参数配置。",
        ],
    )

    assert profiles[0]["score"] > profiles[1]["score"]
    assert "为什么" not in profiles[0]["anchor_terms"]
    assert "sun2000" not in profiles[0]["anchor_terms"]


def test_mppt_purpose_evidence_outranks_unrelated_causal_wording() -> None:
    query = understanding("SUN2000 在组串遮挡场景为什么要启用 MPPT 多峰扫描？")
    query.requested_information = ["CAUSE"]
    unrelated = candidate(
        "unrelated",
        content="由于夜间无光照导致通信中断，延迟升级用于等待供电恢复。",
        rrf=0.88,
    )
    direct = candidate(
        "direct",
        content="组串遮挡会形成多个功率峰值，启用 MPPT 多峰扫描用于执行全局扫描并找到最大功率点。",
        rrf=0.70,
    )

    result = DeterministicEvidenceRerankService().rerank([unrelated, direct], understanding=query)

    assert result.candidates[0].candidate_id == "direct"
    scores = result.diagnostics["score_breakdown"]
    assert scores["direct"]["intent_match"] > scores["unrelated"]["intent_match"]


def test_electrical_work_safety_outranks_generic_mechanical_safety() -> None:
    query = understanding("SUN2000 能否带电拆装线缆，作业时需要哪些防护？")
    query.requested_information = ["SAFETY"]
    generic = candidate(
        "generic",
        content="多人搬运设备时应统一指挥并佩戴防护手套，确保机械作业安全。",
        rrf=0.90,
    )
    direct = candidate(
        "direct",
        content="严禁带电操作，禁止带电安装或拆除线缆；作业人员应使用绝缘工具并穿戴个人防护用品。",
        rrf=0.68,
    )

    result = DeterministicEvidenceRerankService().rerank([generic, direct], understanding=query)

    assert result.candidates[0].candidate_id == "direct"
    scores = result.diagnostics["score_breakdown"]
    assert scores["direct"]["intent_match"] == 1.0
    assert scores["generic"]["intent_match"] < 0.5


def test_installation_guide_wins_byte_equivalent_safety_duplicate() -> None:
    query = understanding("SUN2000 能否带电拆装线缆？")
    query.requested_information = ["SAFETY"]
    content = "严禁带电操作，禁止带电安装或拆除线缆，必须使用绝缘工具。"
    manual = candidate("manual", content=content, rrf=0.80)
    manual.document = SimpleNamespace(document_type="USER_MANUAL", metadata_json={})
    installation = candidate("installation", content=content, rrf=0.80)
    installation.document = SimpleNamespace(document_type="INSTALLATION_GUIDE", metadata_json={})

    result = DeterministicEvidenceRerankService().rerank([manual, installation], understanding=query)

    assert result.candidates[0].candidate_id == "installation"
    scores = result.diagnostics["score_breakdown"]
    assert scores["installation"]["document_purpose_match"] == 1.0


def test_shutdown_verification_requires_wait_and_both_electrical_sides() -> None:
    query = understanding("故障检修下电后应等待多久，并如何确认交直流侧安全？")
    query.requested_information = ["SAFETY", "VERIFICATION"]
    dc_only = candidate(
        "dc-only",
        content="连接直流输入线前应确认直流侧电压处于安全范围。",
        rrf=0.88,
    )
    complete = candidate(
        "complete",
        content="断开交流开关后测量直流电流，再断开直流开关并等待15分钟；使用万用表确认交流端子对地电压安全。",
        rrf=0.72,
    )

    result = DeterministicEvidenceRerankService().rerank([dc_only, complete], understanding=query)

    assert result.candidates[0].candidate_id == "complete"
    scores = result.diagnostics["score_breakdown"]
    assert scores["complete"]["intent_match"] > scores["dc-only"]["intent_match"]


def test_model_coverage_question_prefers_explicit_applicable_model_list() -> None:
    query = understanding("SUN2000-250KTL-H3 是否属于当前手册覆盖的机型？")
    incidental = candidate(
        "incidental",
        content="更新维护章节，调整手册内容架构。SUN2000-250KTL-H3。",
        rrf=0.80,
        exact_model=True,
    )
    model_list = candidate(
        "model-list",
        content="本文主要涉及以下产品型号：SUN2000-250KTL-H1、SUN2000-250KTL-H3、SUN2000-280KTL-H0。",
        rrf=0.80,
        exact_model=True,
    )

    result = DeterministicEvidenceRerankService().rerank([incidental, model_list], understanding=query)
    scores = result.diagnostics["score_breakdown"]

    assert scores["model-list"]["document_purpose_match"] == 1.0, scores
    assert result.candidates[0].candidate_id == "model-list", scores


def test_calculation_question_prefers_formula_over_general_procedure() -> None:
    query = understanding("绝缘阻抗故障位置百分比怎样换算到组件位置？")
    query.requested_information = ["PROCEDURE"]
    procedure = candidate(
        "procedure",
        content="打开告警详情并按步骤逐个接入光伏组串进行故障位置定位。",
        rrf=0.88,
    )
    formula = candidate(
        "formula",
        content="疑似故障位置=光伏组件总数量×可能短路位置百分比值，据此核对组件位置。",
        rrf=0.72,
    )

    result = DeterministicEvidenceRerankService().rerank([procedure, formula], understanding=query)

    assert result.candidates[0].candidate_id == "formula"
    scores = result.diagnostics["score_breakdown"]
    assert scores["formula"]["intent_match"] > scores["procedure"]["intent_match"]


def test_quantity_question_prefers_structured_quantity_field() -> None:
    query = understanding("SUN2000-5KTL-M0 有多少路 MPPT？")
    prose = candidate(
        "prose",
        content="2路PV组串接入2路MPPT电路进行最大功率点跟踪。",
        rrf=0.82,
        exact_model=True,
    )
    table = candidate(
        "table",
        content="技术指标 SUN2000-5KTL-M0，MPPT数量 2。",
        rrf=0.78,
        exact_model=True,
    )

    result = DeterministicEvidenceRerankService().rerank([prose, table], understanding=query)

    assert result.candidates[0].candidate_id == "table"
    assert result.diagnostics["score_breakdown"]["table"]["document_purpose_match"] == 1.0


def test_configuration_intent_rewards_specific_symptom_bundle() -> None:
    query = understanding("SUN2000 直流输入电压高时如何检查光伏组串配置？")
    query.requested_information = ["CONFIGURATION"]
    generic = candidate(
        "generic",
        content="在设置页面检查绝缘阻抗参数和普通组串状态。",
        rrf=0.84,
    )
    direct = candidate(
        "direct",
        content="直流输入电压高时检查光伏组串的串联配置，确认开路电压不超过最大工作电压。",
        rrf=0.78,
    )

    result = DeterministicEvidenceRerankService().rerank([generic, direct], understanding=query)

    assert result.candidates[0].candidate_id == "direct"
    scores = result.diagnostics["score_breakdown"]
    assert scores["direct"]["intent_match"] > scores["generic"]["intent_match"]


def test_unknown_requested_information_is_not_automatically_supported() -> None:
    supported = DeterministicEvidenceRerankService.requested_information_support(
        "普通产品概述与版本说明。",
        ["COMMUNICATION", "TROUBLESHOOTING", "UNRECOGNIZED"],
    )

    assert supported == set()


def test_verification_accepts_manual_wording_for_determining_requirements() -> None:
    supported = DeterministicEvidenceRerankService.requested_information_support(
        "使用背板确定打孔位置，并按要求选用膨胀螺栓。",
        ["VERIFICATION"],
    )

    assert supported == {"VERIFICATION"}


def test_answer_directions_take_one_best_sentence_from_each_source_first() -> None:
    chunks = [
        _retrieved("检查通信参数。确认通信模块状态。必要时重启通信模块。"),
        _retrieved("自动关机判定时间应在通信中断配置页面核对。"),
        _retrieved("处理后确认告警是否消除。"),
    ]

    directions = AnswerGenerationService()._extract_directions(
        chunks,
        ["自动关机判定时间", "通信中断", "配置页面"],
    )

    assert directions[0].startswith("[来源1]")
    assert directions[1].startswith("[来源2]")
    assert directions[2].startswith("[来源3]")
    assert "自动关机判定时间" in directions[1]


def test_answer_excerpt_keeps_alarm_name_cause_and_action_context() -> None:
    chunks = [
        _retrieved(
            "告警ID 103 直流输入电压高。光伏组串串联配置错误会使开路电压高于最大工作电压。"
            "检查光伏阵列串联配置，修正后确认告警消失。"
        )
    ]

    directions = AnswerGenerationService()._extract_directions(
        chunks,
        ["103", "直流输入电压高", "开路电压", "串联配置"],
    )
    answer = " ".join(directions)

    assert "直流输入电压高" in answer
    assert "开路电压" in answer
    assert "串联配置" in answer


def test_evidence_findings_summarize_alarm_row_without_labels() -> None:
    chunks = [
        _retrieved(
            "告警ID 103 DC输入电压高。光伏阵列配置错误，串联的光伏电池板过多，"
            "导致组串开路电压超过逆变器最大工作电压。"
        )
    ]

    findings = AnswerGenerationService()._build_evidence_findings(
        RetrievalQueryRequest(query="告警代码 103 表示什么，应先检查什么？", alarm_code="103"),
        chunks,
    )

    assert findings == [
        "[来源1] 告警含义为直流输入电压高；先检查光伏组串的串联配置，避免开路电压超过逆变器最大工作电压。"
    ]


def test_evidence_findings_keep_fan_action_sequence() -> None:
    chunks = [
        _retrieved("风扇运行时有异常噪声，应清理风扇上的异物；如果仍有异常噪声，需更换风扇。")
    ]

    findings = AnswerGenerationService()._build_evidence_findings(
        RetrievalQueryRequest(query="风扇有异常噪声时怎样处理？"),
        chunks,
    )

    assert "先清理异物" in findings[0]
    assert "再更换风扇" in findings[0]


def test_evidence_findings_keep_shutdown_measurement_bundle() -> None:
    chunks = [
        _retrieved(
            "逆变器下电15分钟以后再操作。使用钳流表直流电流档测量组串直流电流。"
            "使用万用表测量交流端子排对地电压。"
        )
    ]

    findings = AnswerGenerationService()._build_evidence_findings(
        RetrievalQueryRequest(query="检修下电后等待多久，如何确认交直流侧安全？"),
        chunks,
    )
    combined = " ".join(findings)

    assert "等待15min" in combined
    assert "测量直流电流" in combined
    assert "测量交流端子排对地电压" in combined


def test_domain_terms_are_emitted_before_sliding_windows() -> None:
    terms = QuerySignalExtractionService.retrieval_terms(
        "SUN2000 指示灯提示交流侧电网欠压时是什么状态？",
        limit=8,
    )

    assert "电网欠压" in terms
    assert "交流侧环境告警" not in terms
