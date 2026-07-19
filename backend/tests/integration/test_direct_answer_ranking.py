from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from tests.minimax_test_helpers import candidate, understanding


def test_specific_cause_and_action_ranks_above_generic_high_rrf_section():
    query = understanding("通信为什么掉线，怎么处理？")
    query.requested_information = ["CAUSE", "ACTION"]
    broad = candidate("broad", content="产品介绍和通信概述" * 120, rrf=.9)
    broad.source_query_types = {"FULL_SECTION"}
    direct = candidate("direct", content="原因是接线松动；检查端子并重新连接。", rrf=.4)
    result = DeterministicEvidenceRerankService().rerank([broad, direct], understanding=query)
    assert result.candidates[0].candidate_id == "direct"
    assert result.candidates[0].direct_answer_level == "DIRECT_ANSWER"
