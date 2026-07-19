from __future__ import annotations

import json

from task25f_common import build_performance_suite, read_json, write_json


def main() -> int:
    existing = read_json("performance_suite_manifest.json")
    generated = build_performance_suite()
    if existing:
        if existing.get("dataset_sha256") != generated.get("dataset_sha256"):
            raise SystemExit("Task 25F performance suite exists with a different immutable hash")
        result = existing
        status = "TASK25F_PERFORMANCE_SUITE_VERIFIED"
    else:
        result = generated
        write_json("performance_suite_manifest.json", result, overwrite=False)
        status = "TASK25F_PERFORMANCE_SUITE_CREATED"
    if result.get("case_count", 0) < 60 or not result.get("requirements_passed"):
        raise SystemExit("Task 25F performance suite does not satisfy coverage requirements")
    print(json.dumps({
        "status": status,
        "dataset_version": result["dataset_version"],
        "case_count": result["case_count"],
        "dataset_sha256": result["dataset_sha256"],
        "coverage": result["coverage"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
