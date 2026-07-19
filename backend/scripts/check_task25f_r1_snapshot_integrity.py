from __future__ import annotations

import json

from task25f_r1_common import ROOT, RUNTIME, TASK25F_RUNTIME, read_json, sha256_file, sha256_value, write_json

from app.services.rag_raw_channel_snapshot import snapshot_from_dict


PROHIBITED_KEYS = {"vector", "query", "question", "content", "api_key", "authorization", "raw_response"}


def _contains_prohibited(value) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in PROHIBITED_KEYS:
                found.append(str(key))
            found.extend(_contains_prohibited(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_contains_prohibited(item))
    return found


def main() -> int:
    frozen = read_json("task25f_snapshot.json", {})
    hashes = read_json("task25f_hash_manifest.json", {})
    manifest = read_json("channel_snapshot_manifest.json", {})
    snapshot_path = RUNTIME / "channel_snapshots.jsonl"
    rows = [json.loads(line) for line in snapshot_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    invalid_hashes = []
    invalid_channels = []
    for row in rows:
        snapshot = snapshot_from_dict(row)
        if not snapshot.verify():
            invalid_hashes.append(snapshot.snapshot_id)
        if snapshot.channel not in {"EXACT_KEYWORD", "SCOPED_KEYWORD", "RAW_VECTOR", "SEMANTIC_UNIT", "KG_ALIAS"}:
            invalid_channels.append(snapshot.channel)
    task25f_files = []
    for item in hashes.get("files") or []:
        path = ROOT / item["path"]
        task25f_files.append({
            "path": item["path"],
            "exists": path.is_file(),
            "expected_sha256": item.get("sha256"),
            "actual_sha256": sha256_file(path),
            "unchanged": path.is_file() and sha256_file(path) == item.get("sha256"),
        })
    suite = json.loads((TASK25F_RUNTIME / "performance_suite_manifest.json").read_text(encoding="utf-8"))
    prohibited = sorted(set(_contains_prohibited(rows)))
    checks = {
        "frozen_snapshot_present": bool(frozen),
        "case_count_60": manifest.get("case_count") == 60,
        "suite_sha256_unchanged": manifest.get("query_suite_sha256") == suite.get("dataset_sha256") == frozen.get("query_suite", {}).get("sha256"),
        "record_count_matches": manifest.get("channel_record_count") == len(rows),
        "file_hash_matches": manifest.get("snapshot_file_sha256") == sha256_file(snapshot_path),
        "manifest_hash_valid": manifest.get("manifest_hash") == sha256_value({key: value for key, value in manifest.items() if key != "manifest_hash"}),
        "record_hashes_valid": not invalid_hashes,
        "channels_valid": not invalid_channels,
        "task25f_files_unchanged": all(item["unchanged"] for item in task25f_files),
        "no_prohibited_payload_fields": not prohibited,
        "no_vectors": manifest.get("contains_vectors") is False,
        "no_query_text": manifest.get("contains_query_text") is False,
        "no_candidate_content": manifest.get("contains_candidate_content") is False,
    }
    passed = all(checks.values())
    payload = {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "checks": checks,
        "case_count": manifest.get("case_count"),
        "channel_record_count": len(rows),
        "candidate_record_count": sum(len(row.get("candidates") or []) for row in rows),
        "invalid_snapshot_hashes": invalid_hashes,
        "invalid_channels": invalid_channels,
        "prohibited_fields": prohibited,
        "task25f_files": task25f_files,
        "provider_calls_during_integrity_check": 0,
    }
    write_json("snapshot_integrity.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "cases": payload["case_count"],
        "records": payload["channel_record_count"],
        "candidates": payload["candidate_record_count"],
        "invalid_hashes": len(invalid_hashes),
        "task25f_unchanged": checks["task25f_files_unchanged"],
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
