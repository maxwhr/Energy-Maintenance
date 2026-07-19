import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r5", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("R5 browser evidence is missing; run the in-app browser review first");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "exact_model_fast_path",
  "exact_alarm_fast_path",
  "oral_query_understanding",
  "normalized_question_visible",
  "intent_visible",
  "missing_information_visible",
  "active_clarification_visible",
  "clarification_context_merged",
  "multi_query_route_visible",
  "rerank_status_visible",
  "evidence_confidence_visible",
  "multiple_possibilities_visible",
  "no_answer_boundary_visible",
  "citation_page_visible",
  "viewer_read_only",
  "r4_failure_preserved",
  "r5_quality_card_visible",
  "formal_test_blocked_visible",
  "no_secret_rendered",
];

const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (!Array.isArray(evidence.scenarios) || evidence.scenarios.length < 6) failures.push("scenarios");
if (evidence.canary_status !== "CANARY_FAILED") failures.push("canary_status");
if (evidence.formal_test_status !== "NOT_CREATED_CANARY_FAILED") failures.push("formal_test_status");

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
