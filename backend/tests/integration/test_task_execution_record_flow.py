import pytest
from pydantic import ValidationError

from app.schemas.maintenance_workflow import WorkflowTaskRecordCreate


def test_measurement_record_requires_value_and_unit():
    record = WorkflowTaskRecordCreate(
        idempotency_key="record-0001",
        record_type="MEASUREMENT",
        measurements=[{"name": "DC voltage", "value": 600, "unit": "V"}],
    )
    assert record.measurements[0].unit == "V"
    with pytest.raises(ValidationError):
        WorkflowTaskRecordCreate(idempotency_key="record-0002", record_type="MEASUREMENT")

