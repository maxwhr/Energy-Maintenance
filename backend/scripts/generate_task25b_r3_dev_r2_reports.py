from __future__ import annotations

import json
from pathlib import Path

from task25b_r3_dev_r2_common import OUT, ROOT, now_iso


def load(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_report(path: Path, title: str, body: str) -> None:
    path.write_text(f"# {title}\n\nGenerated: {now_iso()}\n\n{body}\n", encoding="utf-8")


def upsert_notice(path: Path, marker: str, body: str) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    marker_index = content.find(marker)
    if marker_index >= 0:
        content = content[:marker_index].rstrip()
    path.write_text(f"{content}\n\n{marker}\n\n{body}\n", encoding="utf-8")


def main() -> None:
    contract = load("metric_contract_audit.json")
    model_alarm = load("model_alarm_metric_audit.json")
    vector = load("vector_heavy_audit.json")
    mode = load("mode_distinctness_v2.json")
    manifest = load("dataset_v3_manifest.json")
    canary = load("canary_result.json")
    quality = load("quality_gate_v3.json")
    coverage = manifest.get("test_v3_coverage") or {}
    docs = ROOT / "docs"

    write_report(
        docs / "25B_R3_DEV_R2_metric_contract_report.md",
        "Task 25B-R3-DEV-R2 Metric Contract Audit",
        "\n".join([
            f"- Single-relevant cases: {contract.get('single_relevant_cases', 0)}",
            f"- Multi-relevant cases: {contract.get('multi_relevant_cases', 0)}",
            f"- v2 cases where fixed raw P@5 is mathematically impossible: {contract.get('impossible_precision_at_5_cases', 0)}",
            "- Raw P@5 remains diagnostic only. Single-relevant cases use Hit@1, Hit@5 and MRR; multi-relevant cases use P@5, R-Precision and Recall@5.",
            "- Surfaced precision and irrelevant-result rate are reported separately from raw ranking metrics.",
        ]),
    )
    write_report(
        docs / "25B_R3_DEV_R2_result_set_refinement_report.md",
        "Task 25B-R3-DEV-R2 Result Set Refinement",
        "\n".join([
            "- Candidate generation retains raw Top-10 for evaluation and audit.",
            "- The user-facing result set is independently refined by section collapse, near-duplicate collapse, a two-per-document cap, score cutoff and dynamic 1-5 result sizing.",
            "- API diagnostics expose raw/surfaced counts, cutoff reason, collapsed groups, and section/document diversity.",
            "- Benchmark expected labels are never returned by ordinary retrieval APIs.",
        ]),
    )
    write_report(
        docs / "25B_R3_DEV_R2_model_alarm_metrics_report.md",
        "Task 25B-R3-DEV-R2 Model and Alarm Metrics",
        "\n".join([
            f"- v2 model coverage gate: {model_alarm.get('model_coverage_gate')}",
            f"- v2 alarm coverage gate: {model_alarm.get('alarm_coverage_gate')}",
            f"- Unfrozen v3 test coverage: model={coverage.get('model_cases', 0)}, alarm={coverage.get('alarm_cases', 0)}.",
            "- N/A is excluded from a metric denominator and is not reported as 0 percent.",
        ]),
    )
    write_report(
        docs / "25B_R3_DEV_R2_vector_heavy_report.md",
        "Task 25B-R3-DEV-R2 Vector-Heavy Audit",
        "\n".join([
            f"- Valid v2 vector-heavy cases: {vector.get('valid_vector_heavy', 0)}",
            f"- Unfrozen v3 test vector-heavy cases: {coverage.get('vector_heavy', 0)}",
            f"- Current train/dev Canary: {canary.get('status', 'NOT_RUN')}",
            "- Vector semantic superiority is not claimed unless the independent vector-heavy gate passes.",
        ]),
    )
    write_report(
        docs / "25B_R3_DEV_R2_mode_distinctness_report.md",
        "Task 25B-R3-DEV-R2 Mode Distinctness Audit",
        "\n".join([
            f"- v2 keyword/vector candidate Jaccard mean: {mode.get('keyword_vector_candidate_jaccard_mean')}",
            f"- v2 keyword/vector rank correlation mean: {mode.get('keyword_vector_rank_correlation_mean')}",
            f"- v2 identical-case rate: {mode.get('identical_case_rate')}",
            f"- Canary mode-distinctness check: {(canary.get('checks') or {}).get('mode_not_all_identical')}",
        ]),
    )
    write_report(
        docs / "25B_R3_DEV_R2_dataset_v3_report.md",
        "Task 25B-R3-DEV-R2 Stratified Dataset v3",
        "```json\n" + json.dumps(manifest, ensure_ascii=False, indent=2) + "\n```\n\n"
        "Pre-freeze drafts (1,200 cases) are retained only as invalid audit history after stratification and query-grounding rebuilds. The current v3 dataset remains unfrozen because Canary did not pass.",
    )
    write_report(
        docs / "25B_R3_DEV_R2_canary_report.md",
        "Task 25B-R3-DEV-R2 Canary",
        "```json\n" + json.dumps(
            {key: canary.get(key) for key in ("status", "cases", "checks", "vector_heavy")},
            ensure_ascii=False,
            indent=2,
        ) + "\n```\n\n"
        "Canary failure strictly prohibits freezing test_v3 and running the one permitted formal v3 quality gate.",
    )
    quality_text = (
        f"Formal quality-gate result: `{quality.get('result')}`."
        if quality
        else "Formal quality gate: NOT EXECUTED. Canary failed and test_v3 is not frozen."
    )
    write_report(
        docs / "25B_R3_DEV_R2_quality_gate_v3_report.md",
        "Task 25B-R3-DEV-R2 v3 Quality Gate",
        quality_text + "\n\nThe failed v2 run is preserved. No formal v3 run, vector rebuild, or reindex of 1,262 vectors was performed.",
    )

    marker = "<!-- Task25B-R3-DEV-R2 -->"
    updates = {
        docs / "25B_R3_DEV_R1_quality_gate_v2_report.md": "R2 froze v2 as a read-only failed baseline. It was neither overwritten nor rerun.",
        docs / "25B_R3_DEV_R1_benchmark_label_integrity_report.md": "R2 confirms that each v2 test case has one relevant chunk, making fixed P@5 unsuitable as a universal single-relevant hard gate.",
        docs / "25B_R2_full_reindex_go_no_go_report.md": "R2 did not execute a formal full rebuild, clear pilot_r2, or rebuild the 1,262 vectors.",
        docs / "09_testing_acceptance_and_quality_spec.md": "Task 25B-R3-DEV-R2 preserves raw P@5, evaluates single-relevant cases with Hit/MRR, evaluates multi-relevant cases with precision/recall, and separately reports surfaced precision and irrelevant-result rate.",
        docs / "12_functional_design_specification.md": "Task 25B-R3-DEV-R2 retrieval APIs return raw/surfaced counts, cutoff reason, collapsed groups, and section/document diversity; ordinary APIs do not return benchmark expected labels.",
        docs / "19_delivery_checklist.md": "Task 25B-R3-DEV-R2 permits one formal v3 quality run only after Canary passes and test_v3 is frozen. Canary failure prohibits that run.",
        ROOT / "README.md": "Task 25B-R3-DEV-R2 adds result-set refinement and a metric contract for Chinese Pilot retrieval. The current v3 Canary failed, so vector semantic superiority is not claimed.",
        ROOT / "backend" / "README.md": "Task 25B-R3-DEV-R2 separates raw ranking from surfaced results. test_v3 can be frozen and formally evaluated only after Canary passes.",
    }
    for path, body in updates.items():
        upsert_notice(path, marker, body)
    print(json.dumps({"status": "PASSED", "reports": 8, "canary": canary.get("status"), "quality_gate": quality.get("result", "NOT_RUN")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
