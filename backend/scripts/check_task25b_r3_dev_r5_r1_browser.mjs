import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r5_r1", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("R5-R1 browser evidence is missing; run the in-app browser review first");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "quality_page_visible",
  "baseline_frozen_visible",
  "structured_probe_visible",
  "rerank_failure_visible",
  "raw_vector_probe_visible",
  "kg_alias_disabled_visible",
  "rrf_vote_cap_visible",
  "canary_blocked_visible",
  "formal_test_blocked_visible",
  "search_page_visible",
  "fast_path_query_submitted",
  "query_diagnostics_visible",
  "requested_channels_visible",
  "actual_channels_visible",
  "fallback_status_visible",
  "viewer_read_only_boundary_verified",
  "no_secret_rendered",
];

const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (!Array.isArray(evidence.scenarios) || evidence.scenarios.length < 2) failures.push("scenarios");
if (evidence.canary_status !== "BLOCKED_PRECANARY") failures.push("canary_status");
if (evidence.formal_test_status !== "NOT_CREATED_CANARY_NOT_PASSED") failures.push("formal_test_status");

const result = {
  status: failures.length ? "FAILED" : "PASSED",
  evidence_path: path.relative(root, evidencePath),
  failures,
  scenarios: evidence.scenarios?.length ?? 0,
  canary_status: evidence.canary_status,
  formal_test_status: evidence.formal_test_status,
};
console.log(JSON.stringify(result));
process.exit(failures.length ? 2 : 0);
