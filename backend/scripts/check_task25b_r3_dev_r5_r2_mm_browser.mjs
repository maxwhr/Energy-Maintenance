import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r5_r2_mm", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("R5-R2-MM browser evidence is missing; run the in-app browser review first");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "quality_page_visible",
  "r5_r1_baseline_visible",
  "minimax_model_status_visible",
  "query_understanding_status_visible",
  "deterministic_rerank_status_visible",
  "tiebreak_status_visible",
  "circuit_breaker_status_visible",
  "canary_status_visible",
  "formal_status_visible",
  "vector_unchanged_visible",
  "search_page_visible",
  "fast_path_visible",
  "safe_fallback_visible",
  "citation_visible",
  "viewer_read_only_boundary_verified",
  "no_secret_rendered",
];
const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (evidence.canary_status !== "CANARY_NOT_RUN_QUERY_GATE_FAILED") failures.push("canary_status");
if (evidence.formal_test_status !== "NOT_RUN_CANARY_FAILED_OR_NOT_RUN") failures.push("formal_test_status");
const result = {
  status: failures.length ? "FAILED" : "PASSED",
  evidence_path: path.relative(root, evidencePath),
  failures,
  console_errors: evidence.console_errors?.length ?? -1,
  page_errors: evidence.page_errors?.length ?? -1,
  unexpected_network_failures: evidence.unexpected_network_failures?.length ?? -1,
};
console.log(JSON.stringify(result));
process.exit(failures.length ? 2 : 0);
