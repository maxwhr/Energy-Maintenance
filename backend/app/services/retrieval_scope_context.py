from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalScopeContext:
    scope: object
    fingerprint: str

    @classmethod
    def from_scope(cls, scope) -> "RetrievalScopeContext":
        payload = scope.public_dict()
        fingerprint = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(scope=scope, fingerprint=fingerprint)
