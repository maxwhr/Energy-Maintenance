import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r4", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("R4 browser evidence is missing; run the in-app browser review first");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "r2_failure_preserved", "r3_failure_preserved", "semantic_unit_types_visible",
  "source_locator_visible", "partition_isolated", "typed_anchor_scores_visible",
  "grounded_canary_visible", "iteration_visible", "viewer_read_only", "no_secret_rendered",
];
const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (!Number.isInteger(evidence.iteration) || evidence.iteration < 1 || evidence.iteration > 2) failures.push("iteration");
if (!["CANARY_PASSED", "CANARY_FAILED"].includes(evidence.canary_status)) failures.push("canary_status");
if (typeof evidence.candidate_recall_at_50 !== "number") failures.push("candidate_recall_at_50");

const result = {
  status: failures.length ? "FAILED" : "PASSED",
  evidence_path: path.relative(root, evidencePath), failures,
  canary_status: evidence.canary_status, iteration: evidence.iteration,
  candidate_recall_at_50: evidence.candidate_recall_at_50,
};
console.log(JSON.stringify(result));
process.exit(failures.length ? 2 : 0);
