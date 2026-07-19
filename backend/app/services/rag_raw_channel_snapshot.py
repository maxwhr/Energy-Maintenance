from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any



def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


ALLOWED_SNAPSHOT_CHANNELS = {
    "EXACT_KEYWORD",
    "SCOPED_KEYWORD",
    "RAW_VECTOR",
    "SEMANTIC_UNIT",
    "KG_ALIAS",
}


@dataclass(frozen=True, slots=True)
class RawRetrievalCandidateSnapshot:
    provider_candidate_id: str
    evidence_source_type: str
    score: float
    rank: int
    metadata_hash: str
    document_id: str
    chunk_id: str
    semantic_unit_id: str | None = None
    section_id: str | None = None
    source_chunk_ids: tuple[str, ...] = field(default_factory=tuple)

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_chunk_ids"] = list(self.source_chunk_ids)
        return value


@dataclass(frozen=True, slots=True)
class RawRetrievalChannelSnapshot:
    snapshot_id: str
    case_id: str
    query_hash: str
    scope_fingerprint: str
    planner_version: str
    retrieval_config_version: str
    channel: str
    variant_id: str
    variant_type: str
    variant_hash: str
    collection: str
    partition: str
    top_k: int
    filter_hash: str
    vector_hash: str | None
    response_status: str
    provider_request_hash: str
    candidates: tuple[RawRetrievalCandidateSnapshot, ...]
    captured_at: str
    error_type: str | None = None
    snapshot_hash: str = ""

    @classmethod
    def create(cls, **values: Any) -> "RawRetrievalChannelSnapshot":
        channel = str(values["channel"])
        if channel not in ALLOWED_SNAPSHOT_CHANNELS:
            raise ValueError(f"unsupported snapshot channel: {channel}")
        candidates = tuple(values.get("candidates") or ())
        captured_at = str(values.get("captured_at") or datetime.now(timezone.utc).isoformat())
        body = {
            **{key: value for key, value in values.items() if key not in {"snapshot_id", "snapshot_hash", "captured_at"}},
            "channel": channel,
            "candidates": [item.public_dict() for item in candidates],
            "captured_at": captured_at,
            "error_type": str(values["error_type"]) if values.get("error_type") else None,
        }
        snapshot_id = str(values.get("snapshot_id") or stable_hash(body))
        snapshot_hash = stable_hash({**body, "snapshot_id": snapshot_id})
        return cls(
            snapshot_id=snapshot_id,
            case_id=str(values["case_id"]),
            query_hash=str(values["query_hash"]),
            scope_fingerprint=str(values["scope_fingerprint"]),
            planner_version=str(values["planner_version"]),
            retrieval_config_version=str(values["retrieval_config_version"]),
            channel=channel,
            variant_id=str(values["variant_id"]),
            variant_type=str(values["variant_type"]),
            variant_hash=str(values["variant_hash"]),
            collection=str(values["collection"]),
            partition=str(values["partition"]),
            top_k=int(values["top_k"]),
            filter_hash=str(values["filter_hash"]),
            vector_hash=str(values["vector_hash"]) if values.get("vector_hash") else None,
            response_status=str(values["response_status"]),
            provider_request_hash=str(values["provider_request_hash"]),
            candidates=candidates,
            captured_at=captured_at,
            error_type=str(values["error_type"]) if values.get("error_type") else None,
            snapshot_hash=snapshot_hash,
        )

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidates"] = [item.public_dict() for item in self.candidates]
        return value

    def verify(self) -> bool:
        value = self.public_dict()
        expected = value.pop("snapshot_hash")
        return stable_hash(value) == expected


def snapshot_from_dict(value: dict[str, Any]) -> RawRetrievalChannelSnapshot:
    candidates = tuple(
        RawRetrievalCandidateSnapshot(
            provider_candidate_id=str(item["provider_candidate_id"]),
            evidence_source_type=str(item["evidence_source_type"]),
            score=float(item["score"]),
            rank=int(item["rank"]),
            metadata_hash=str(item["metadata_hash"]),
            document_id=str(item["document_id"]),
            chunk_id=str(item["chunk_id"]),
            semantic_unit_id=str(item["semantic_unit_id"]) if item.get("semantic_unit_id") else None,
            section_id=str(item["section_id"]) if item.get("section_id") else None,
            source_chunk_ids=tuple(str(source_id) for source_id in item.get("source_chunk_ids") or ()),
        )
        for item in value.get("candidates") or ()
    )
    return RawRetrievalChannelSnapshot(
        snapshot_id=str(value["snapshot_id"]),
        case_id=str(value["case_id"]),
        query_hash=str(value["query_hash"]),
        scope_fingerprint=str(value["scope_fingerprint"]),
        planner_version=str(value["planner_version"]),
        retrieval_config_version=str(value["retrieval_config_version"]),
        channel=str(value["channel"]),
        variant_id=str(value["variant_id"]),
        variant_type=str(value["variant_type"]),
        variant_hash=str(value["variant_hash"]),
        collection=str(value["collection"]),
        partition=str(value["partition"]),
        top_k=int(value["top_k"]),
        filter_hash=str(value["filter_hash"]),
        vector_hash=str(value["vector_hash"]) if value.get("vector_hash") else None,
        response_status=str(value["response_status"]),
        provider_request_hash=str(value["provider_request_hash"]),
        candidates=candidates,
        captured_at=str(value["captured_at"]),
        error_type=str(value["error_type"]) if value.get("error_type") else None,
        snapshot_hash=str(value["snapshot_hash"]),
    )
