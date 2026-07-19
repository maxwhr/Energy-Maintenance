from tests.r5_r5_test_helpers import understand


def test_cause_and_action_form_troubleshooting_primary():
    result = understand("通信为什么掉线，应该怎么排查处理？")
    assert result.primary_intent == "TROUBLESHOOTING"
    assert {"CAUSE", "ACTION"}.issubset(result.requested_information)


def test_prerequisite_action_verification_form_procedure():
    result = understand("更换熔丝前要准备什么，换完怎么确认？")
    assert result.primary_intent == "PROCEDURE"
    assert {"PREREQUISITE", "ACTION", "VERIFICATION", "SAFETY"}.issubset(result.requested_information)
