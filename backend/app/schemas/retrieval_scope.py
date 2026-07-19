from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    scope_id: str
    corpus_type: str
    normalized_language: str | None
    allowed_document_ids: tuple[UUID, ...]
    required_document_status: str
    required_chunk_status: str
    required_approval_mode: tuple[str, ...]
    approved_for_pilot: bool
    current_version_only: bool
    collection_name: str
    partition_name: str
    include_unknown_language: bool = False
    include_alternate_language: bool = False
    include_test_fixture: bool = False
    include_marketing: bool = False
    include_superseded: bool = False
    manufacturer: str | None = None
    product_families: tuple[str, ...] = ()
    device_type: str | None = None
    allowed_source_types: tuple[str, ...] = ()

    def public_dict(self) -> dict:
        value = asdict(self)
        value["allowed_document_ids"] = [str(item) for item in self.allowed_document_ids]
        value["required_approval_mode"] = list(self.required_approval_mode)
        value["product_families"] = list(self.product_families)
        value["allowed_source_types"] = list(self.allowed_source_types)
        return value


CHINESE_ENGINEERING_PILOT_SCOPE_ID = "chinese_engineering_pilot_r2"
HUAWEI_SUN2000_COMPETITION_SCOPE_ID = "huawei_sun2000_competition_v1"
