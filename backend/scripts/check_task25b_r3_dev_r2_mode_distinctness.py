from __future__ import annotations

import json
from statistics import fmean

from task25b_r3_dev_r2_common import OUT, now_iso


def main() -> None:
    path = OUT / "v2_mode_overlap.json"
    if not path.exists():
        raise SystemExit("run v2 forensics before mode-distinctness audit")
    cases = json.loads(path.read_text(encoding="utf-8"))
    overlap = [value["candidate_jaccard"].get("keyword_vector", 1.0) for value in cases.values()]
    correlation = [value["mode_rank_correlation"].get("keyword_vector") for value in cases.values()]
    correlation = [value for value in correlation if value is not None]
    identical = sum(value["candidate_jaccard"].get("keyword_vector", 1.0) == 1.0 for value in cases.values())
    payload = {"generated_at": now_iso(), "source": "v2 read-only result snapshot", "case_count": len(cases),
               "keyword_vector_candidate_jaccard_mean": round(fmean(overlap), 6) if overlap else None,
               "keyword_vector_rank_correlation_mean": round(fmean(correlation), 6) if correlation else None,
               "identical_keyword_vector_cases": identical, "identical_case_rate": round(identical / len(cases), 6) if cases else 0.0,
               "gate": "FAILED_BASELINE_REQUIRES_V3_VECTOR_HEAVY_PROBES" if identical else "BASELINE_DIFFERENT"}
    (OUT / "mode_distinctness_v2.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", **payload}, ensure_ascii=False))


if __name__ == "__main__":
    main()
