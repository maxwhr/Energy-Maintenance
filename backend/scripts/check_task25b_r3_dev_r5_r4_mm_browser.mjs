import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r3_dev_r5_r4_mm", "browser_review.json");

if (!fs.existsSync(evidencePath)) {
  console.error("R5-R4-MM browser evidence is missing; run the in-app browser review first");
  process.exit(2);
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredTrue = [
  "quality_page_visible",
  "fast_path_visible",
  "deterministic_query_understanding_visible",
  "deterministic_canonicalization_visible",
  "ambiguity_options_visible",
  "optional_minimax_visible",
  "safe_fallback_visible",
  "clarification_template_visible",
  "conversation_context_merge_visible",
  "retrieval_plan_visible",
  "citation_visible",
  "multiple_possibilities_visible",
  "no_answer_visible",
  "deterministic_canary_status_visible",
  "optional_minimax_status_visible",
  "viewer_read_only_boundary_verified",
  "no_secret_rendered",
];

const failures = requiredTrue.filter((key) => evidence[key] !== true);
for (const key of ["console_errors", "page_errors", "unexpected_network_failures"]) {
  if (!Array.isArray(evidence[key]) || evidence[key].length !== 0) failures.push(key);
}
if (evidence.selected_runtime_model !== "deterministic-first") failures.push("selected_runtime_model");
if (evidence.minimax_role !== "optional_ambiguity_resolver") failures.push("minimax_role");
if (evidence.full_reindex !== false) failures.push("full_reindex");
if (evidence.viewer_write_controls_visible !== false) failures.push("viewer_write_controls_visible");

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
