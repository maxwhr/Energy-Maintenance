from pydantic import BaseModel

from app.schemas.structured_model import StructuredModelRequest
from app.services.structured_model_call_service import StructuredModelCallService


class P(BaseModel):
    value: int


def test_capability_mode_is_cached_after_success():
    seen = []
    service = StructuredModelCallService(model_call=lambda _request, mode: seen.append(mode) or '{"value":1}')
    request = StructuredModelRequest(purpose="probe", messages=[{"role": "user", "content": "x"}], response_schema=P.model_json_schema(), schema_name="p")
    assert service.call(request, P).success
    assert seen == ["JSON_SCHEMA"]
