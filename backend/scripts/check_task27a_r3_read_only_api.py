from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import func, select


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models import QARecord  # noqa: E402


DATASET_PATH = BACKEND_ROOT / "tests" / "fixtures" / "task27a_huawei_sun2000_engineering_candidate_v1.json"
EXPECTED_DATASET_HASH = "9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0"
CASE_IDS = (
    "HUAWEI-ALARM-001",
    "HUAWEI-COMM-003",
    "HUAWEI-DC-002",
    "HUAWEI-SAFETY-001",
    "HUAWEI-SAFETY-002",
    "HUAWEI-OOS-001",
    "HUAWEI-OOS-002",
)


def _post_json(url: str, payload: dict[str, Any], *, token: str | None, timeout: float) -> dict[str, Any]:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local acceptance URL is explicit.
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"cannot reach {url}: {exc.reason}") from exc


def _strict_contains(text: str, point: str) -> bool:
    return "".join(str(point).casefold().split()) in "".join(str(text).casefold().split())


def _qa_count() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(QARecord)) or 0)


def run(base_url: str, username: str, password: str, timeout: float) -> dict[str, Any]:
    raw = DATASET_PATH.read_bytes()
    dataset_hash = hashlib.sha256(raw).hexdigest()
    if dataset_hash != EXPECTED_DATASET_HASH:
        raise RuntimeError(f"DATASET_INTEGRITY_FAILURE: {dataset_hash}")
    dataset = json.loads(raw.decode("utf-8"))
    cases = {item["case_id"]: item for item in dataset["cases"]}

    login = _post_json(
        f"{base_url}/api/auth/login",
        {"username": username, "password": password},
        token=None,
        timeout=timeout,
    )
    token = str((login.get("data") or {}).get("access_token") or "")
    if not token:
        raise RuntimeError("login did not return an access token")

    qa_before = _qa_count()
    results: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        case = cases[case_id]
        request_id = f"task27a-r3-api-{case_id.casefold()}"
        response = _post_json(
            f"{base_url}/api/retrieval/query-aware-search",
            {
                "query": case["query"],
                "request_id": request_id,
                "retrieval_mode": "fast",
                "top_k": 5,
                "enable_llm": False,
                "allow_real_api": False,
                "persist_result": False,
            },
            token=token,
            timeout=timeout,
        )
        if response.get("code") != 200:
            raise AssertionError(f"{case_id}: response code is not 200")
        data = response.get("data") or {}
        references = list(data.get("references") or [])
        chunk_ids = [str(item.get("chunk_id") or "") for item in references]
        combined_answer = "\n".join([
            str(data.get("answer") or ""),
            str(data.get("message") or ""),
            *[str(item) for item in data.get("suggested_steps") or []],
            *[str(item) for item in data.get("safety_notes") or []],
        ])
        missing_points = [
            point for point in case["required_answer_points"] if not _strict_contains(combined_answer, point)
        ]
        expected_present = bool(set(case["expected_chunk_ids"]).intersection(chunk_ids))

        if data.get("request_id") != request_id or not data.get("trace_id"):
            raise AssertionError(f"{case_id}: request/trace identity is incomplete")
        if data.get("persistence_status") != "skipped_preview":
            raise AssertionError(f"{case_id}: persist_result=false was not reported as skipped_preview")
        if case["should_abstain"]:
            if not data.get("abstained") or references or data.get("retrieved_chunks"):
                raise AssertionError(f"{case_id}: unsupported scope did not abstain cleanly")
        elif not expected_present or missing_points:
            raise AssertionError(
                f"{case_id}: expected evidence/strict answer points missing; "
                f"evidence={expected_present}, missing_points={missing_points}"
            )

        results.append({
            "case_id": case_id,
            "utf8_query_preserved": data.get("original_query") == case["query"],
            "reference_count": len(references),
            "expected_chunk_rank": (
                next((index for index, value in enumerate(chunk_ids, start=1) if value in case["expected_chunk_ids"]), None)
            ),
            "strict_answer_points_missing": missing_points,
            "abstained": bool(data.get("abstained")),
            "persistence_status": data.get("persistence_status"),
            "trace_present": bool(data.get("trace_id")),
        })

    qa_after = _qa_count()
    if qa_after != qa_before:
        raise AssertionError(f"read-only API regression changed QA count: {qa_before} -> {qa_after}")
    if not all(item["utf8_query_preserved"] for item in results):
        raise AssertionError("one or more UTF-8 queries changed in transit")
    return {
        "status": "passed",
        "mode": "read_only_preview",
        "dataset_sha256": dataset_hash,
        "case_count": len(results),
        "qa_count_before": qa_before,
        "qa_count_after": qa_after,
        "external_provider_calls": 0,
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Task 27A-R3 UTF-8 read-only API regression")
    parser.add_argument("--base-url", default="http://127.0.0.1:8014")
    parser.add_argument("--username", default=os.getenv("TASK27A_ADMIN_USERNAME", "admin"))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    password = os.getenv("TASK27A_ADMIN_PASSWORD") or os.getenv("FULL_SMOKE_ADMIN_PASSWORD")
    if not password:
        raise RuntimeError("TASK27A_ADMIN_PASSWORD or FULL_SMOKE_ADMIN_PASSWORD is required")
    result = run(args.base_url.rstrip("/"), args.username, password, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
