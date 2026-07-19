from __future__ import annotations

import json
from task25b_common import RUNTIME, write_result


def load(name):
    path = RUNTIME / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def main() -> int:
    required = {name: load(name) for name in ("embedding_real.json", "dashvector_real.json", "retrieval_evaluation.json", "multimodal_retrieval.json")}
    checks = {name: bool(value and value.get("status") == "PASSED") for name, value in required.items()}
    result = {"status": "FULL_PASS" if all(checks.values()) else "PARTIAL_OR_BLOCKED", "checks": checks, "missing": [name for name, value in required.items() if value is None]}
    write_result("quality_gate.json", result)
    return 0 if result["status"] == "FULL_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
