from app.services.clarification_question_template_service import ClarificationQuestionTemplateService
from app.services.multimodal_clarification_service import MultimodalClarificationService


def test_templates_are_bounded_prioritized_and_not_free_text():
    service = ClarificationQuestionTemplateService()
    questions = service.questions([
        "DEVICE_MODEL", "COMMUNICATION_METHOD", "SPECIFIC_SYMPTOM", "ALARM_CODE"
    ])
    assert questions == [
        "请说明具体表现是不发电、无法上电、指示灯异常，还是平台连接不上。",
        "请补充设备显示的告警代码或告警名称。",
        "请说明使用的是 WiFi、4G、以太网还是 RS485 通信。",
    ]


def test_empty_missing_slots_produces_no_question():
    assert ClarificationQuestionTemplateService().first([]) is None


def test_multimodal_clarification_uses_safe_templates() -> None:
    questions = MultimodalClarificationService().build(
        missing_information=["device_model"],
        conflicts=[{"conflict_type": "DEVICE_MODEL_CONFLICT"}],
        image_quality_flags=["possibly_blurry"],
    )

    assert {item["question_type"] for item in questions} == {"DEVICE_MODEL", "CONFLICT", "IMAGE_QUALITY"}
    assert all(item["safe_template"] is True for item in questions)
    assert not any("拆卸" in item["question"] or "带电" in item["question"] for item in questions)
