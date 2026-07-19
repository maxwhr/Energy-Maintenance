from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.record_center import RecordCenterItemIdentity, RecordCenterRecordType


def test_record_center_identity_contract_is_typed() -> None:
    identity = RecordCenterItemIdentity(
        record_type=RecordCenterRecordType.QA,
        record_id=uuid4(),
        primary_timestamp=datetime.now(timezone.utc),
        title_key="question",
        summary_key="answer",
        source_table="qa_records",
        source_priority=0,
    )
    assert identity.record_type is RecordCenterRecordType.QA
    assert identity.source_table == "qa_records"
    assert identity.workflow_id is None

