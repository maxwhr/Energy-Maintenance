from pydantic import BaseModel

from app.schemas.structured_model import StructuredModelRequest
from app.services.structured_model_call_service import StructuredModelCallService


class Payload(BaseModel):
    ok: bool


def test_structured_model_call_validates_payload():
    request = StructuredModelRequest(purpose="test", messages=[{"role": "user", "content": "json"}], response_schema=Payload.model_json_schema(), schema_name="payload")
    result = StructuredModelCallService(model_call=lambda _request, _mode: '{"ok":true}').call(request, Payload)
    assert result.success and result.parsed_payload == {"ok": True}
