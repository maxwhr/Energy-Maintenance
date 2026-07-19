import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r5_r3_mm", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("R5-R3-MM browser evidence is missing; run the in-app browser review first");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "quality_page_visible",
  "r5_r2_baseline_visible",
  "r5_r3_contract_status_visible",
  "schema_v2_status_visible",
  "same_sample_model_ab_visible",
  "deterministic_runtime_visible",
  "context_merge_status_visible",
  "planner_status_visible",
  "tiebreak_default_disabled_visible",
  "canary_blocked_visible",
  "formal_not_created_visible",
  "vector_read_only_unchanged_visible",
  "search_page_visible",
  "deterministic_query_understanding_visible",
  "citation_visible",
  "viewer_read_only_boundary_verified",
  "no_secret_rendered",
];

const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (evidence.final_status !== "QUERY_UNDERSTANDING_CONTRACT_NOT_READY") failures.push("final_status");
if (evidence.selected_runtime_model !== "deterministic") failures.push("selected_runtime_model");
if (evidence.canary_executed_cases !== 0) failures.push("canary_executed_cases");
if (evidence.formal_test_status !== "NOT_CREATED_CONTRACT_NOT_READY") failures.push("formal_test_status");

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
