from types import SimpleNamespace

import pytest

from app.models import KnowledgeDocument
from app.schemas.review import VendorOfficialBatchApproveRequest, VendorOfficialWithdrawRequest
from app.services.alarm_knowledge_extraction_service import AlarmKnowledgeExtractionService
from app.services.equipment_classification_service import EquipmentClassificationService
from app.services.retrieval_pilot_service import RetrievalPilotService
from app.services.review_service import ReviewService, ReviewServiceError
from scripts.task25b_r2_u2_common import is_official_url


def vendor_document(**metadata_overrides) -> KnowledgeDocument:
    metadata = {
        "vendor_source_verified": True,
        "content_parse_verified": True,
        "quality_status": "READY_FOR_DRAFT_IMPORT",
        "marketing_only": False,
        "duplicate": False,
        "ocr_required": False,
        **metadata_overrides,
    }
    return KnowledgeDocument(
        title="Huawei official manual",
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        document_type="manual",
        source_type="vendor_official",
        parse_status="parsed",
        review_status="pending_review",
        status="active",
        metadata_json=metadata,
    )


def test_official_url_whitelist_rejects_third_party_and_insecure_urls():
    assert is_official_url("https://solar.huawei.com/en/downloadcenter/manual.pdf")
    assert is_official_url("https://download.huawei.com/dl/user-manual.pdf")
    assert not is_official_url("http://solar.huawei.com/manual.pdf")
    assert not is_official_url("https://huawei.example.com/manual.pdf")
    assert not is_official_url("https://example.com/huawei/manual.pdf")


def test_vendor_document_requires_verified_quality_before_human_approval():
    ReviewService._validate_vendor_official(vendor_document())
    with pytest.raises(ReviewServiceError):
        ReviewService._validate_vendor_official(vendor_document(marketing_only=True))
    with pytest.raises(ReviewServiceError):
        ReviewService._validate_vendor_official(vendor_document(ocr_required=True))
    with pytest.raises(ReviewServiceError):
        ReviewService._validate_vendor_official(vendor_document(content_parse_verified=False))


def test_partition_preflight_accepts_existing_collection_with_isolated_partition():
    service = RetrievalPilotService.__new__(RetrievalPilotService)
    service.settings = SimpleNamespace(
        TASK25B_R2_PILOT_ENABLED=True,
        TASK25B_R2_ALLOW_PILOT_INDEX=True,
        TASK25B_ALLOW_REAL_API=True,
        DASHVECTOR_USE_PARTITIONS=True,
        DASHVECTOR_PHYSICAL_COLLECTION="energy_kn_te_v4_1024_v1",
        DASHVECTOR_PILOT_COLLECTION="unused_collection_name",
        DASHVECTOR_PILOT_PARTITION="pilot_r2",
    )
    result = service.pilot_index_preflight(
        allow_real_api=True,
        pilot_only=True,
        approved_only=True,
    )
    assert result["accepted"] is True
    assert result["isolation_mode"] == "partition"
    assert result["pilot_collection"] == "energy_kn_te_v4_1024_v1"
    assert result["pilot_partition"] == "pilot_r2"
    assert result["full_reindex_executed"] is False


def test_partition_preflight_blocks_missing_partition():
    service = RetrievalPilotService.__new__(RetrievalPilotService)
    service.settings = SimpleNamespace(
        TASK25B_R2_PILOT_ENABLED=True,
        TASK25B_R2_ALLOW_PILOT_INDEX=True,
        TASK25B_ALLOW_REAL_API=True,
        DASHVECTOR_USE_PARTITIONS=True,
        DASHVECTOR_PHYSICAL_COLLECTION="energy_kn_te_v4_1024_v1",
        DASHVECTOR_PILOT_COLLECTION="unused_collection_name",
        DASHVECTOR_PILOT_PARTITION="",
    )
    result = service.pilot_index_preflight(
        allow_real_api=True,
        pilot_only=True,
        approved_only=True,
    )
    assert result["accepted"] is False
    assert "pilot_partition_not_configured" in result["failures"]


def test_u3_alarm_extraction_accepts_real_heading_codes_and_never_invents_codes():
    service = AlarmKnowledgeExtractionService()
    result = service.extract(
        title="SmartLogger Alarm Reference",
        text="# 1100 Active Power Scheduling Instruction Exception\n\nStep 1 Power off the device safely.\n\n# Insulation resistance fault\n\nCheck the PV string.",
        device_models=["SmartLogger3000"],
    )
    assert result["explicit_alarm_codes"] == ["1100"]
    assert result["troubleshooting_steps"] == 1
    assert result["safety_actions"] >= 1
    assert all(item["alarm_identifier_type"] == "name_only" for item in result["named_alarms"])


def test_u3_equipment_classification_does_not_map_luna_or_merc_to_inverter():
    assert EquipmentClassificationService.classify("LUNA2000 battery ESS") == ["energy_storage"]
    assert EquipmentClassificationService.classify("MERC-1300W-P optimizer") == ["power_optimizer"]
    assert EquipmentClassificationService.classify("FusionSolar SmartPVMS") == ["management_platform"]


def test_u3_batch_approval_schema_caps_each_human_action_at_ten_documents():
    from uuid import uuid4
    from pydantic import ValidationError

    VendorOfficialBatchApproveRequest(document_ids=[uuid4() for _ in range(10)])
    with pytest.raises(ValidationError):
        VendorOfficialBatchApproveRequest(document_ids=[uuid4() for _ in range(11)])


def test_approval_withdrawal_requires_a_material_reason():
    from pydantic import ValidationError

    request = VendorOfficialWithdrawRequest(reason="Unexpected approval detected during quality review")
    assert request.target_status == "pending_review"
    with pytest.raises(ValidationError):
        VendorOfficialWithdrawRequest(reason="too short")


def test_approval_withdrawal_marks_document_for_individual_review(monkeypatch):
    from uuid import uuid4

    document = vendor_document()
    document.id = uuid4()
    document.review_status = "approved"
    document.metadata_json = {
        **(document.metadata_json or {}),
        "approved_for_pilot": True,
        "quality_status": "READY_FOR_HUMAN_REVIEW",
    }
    reviewer = SimpleNamespace(id=uuid4(), role="admin", username="admin")
    service = ReviewService.__new__(ReviewService)
    service.repository = SimpleNamespace(
        get_document=lambda _: document,
        count_vector_indexes=lambda *_args, **_kwargs: 0,
    )
    captured = {}

    def fake_review_document(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(service, "_review_document", fake_review_document)
    result = service.withdraw_vendor_official_approval(
        document.id,
        target_status="pending_review",
        reason="Unexpected long manual approval requires individual quality review",
        reviewer=reviewer,
    )

    assert result == {"ok": True}
    assert captured["action"] == "withdraw_approval"
    assert captured["after_status"] == "pending_review"
    assert captured["audit_metadata"]["automatic_operation"] is False
    assert document.metadata_json["approved_for_pilot"] is False
    assert document.metadata_json["requires_individual_review"] is True
    assert document.metadata_json["pilot_index_excluded"] is True
    assert document.metadata_json["quality_status"] == "REQUIRE_INDIVIDUAL_REVIEW"


def test_approval_withdrawal_refuses_document_with_pilot_vectors():
    from uuid import uuid4

    document = vendor_document()
    document.id = uuid4()
    document.review_status = "approved"
    reviewer = SimpleNamespace(id=uuid4(), role="expert", username="expert")
    service = ReviewService.__new__(ReviewService)
    service.repository = SimpleNamespace(
        get_document=lambda _: document,
        count_vector_indexes=lambda *_args, **_kwargs: 1,
    )

    with pytest.raises(ReviewServiceError, match="Pilot rollback"):
        service.withdraw_vendor_official_approval(
            document.id,
            target_status="pending_review",
            reason="Unexpected approval must be withdrawn after Pilot rollback",
            reviewer=reviewer,
        )
