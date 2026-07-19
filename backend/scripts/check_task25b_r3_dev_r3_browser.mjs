import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r3", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("browser evidence is missing; run the in-app browser review before this checker");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "r2_failure_preserved",
  "diagnostic_visible",
  "raw_semantic_separated",
  "partition_isolated",
  "semantic_gain_visible",
  "actual_route_visible",
  "viewer_read_only",
  "no_secret_rendered",
];
const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (evidence.canary_status !== "CANARY_FAILED") failures.push("canary_status");
if (Number(evidence.candidate_recall_at_50) !== 0.444444) failures.push("candidate_recall_at_50");

const result = {
  status: failures.length ? "FAILED" : "PASSED",
  evidence_path: path.relative(root, evidencePath),
  failures,
  canary_status: evidence.canary_status,
  candidate_recall_at_50: evidence.candidate_recall_at_50,
};
console.log(JSON.stringify(result));
process.exit(failures.length ? 2 : 0);
