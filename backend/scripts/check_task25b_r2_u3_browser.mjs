import fs from "node:fs";
import path from "node:path";

const backend = path.resolve(import.meta.dirname, "..");
const root = path.resolve(backend, "..");
const evidencePath = path.join(root, ".runtime", "task25b_r2_u3", "browser.json");

if (!fs.existsSync(evidencePath)) {
  throw new Error("U3 in-app Browser evidence is missing; run the Browser skill acceptance first");
}

const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const requiredChecks = [
  "official_document_review_page",
  "batch_limit_and_confirmation",
  "viewer_approval_forbidden",
  "engineer_approval_forbidden",
  "benchmark_review_queue",
  "corpus_and_pilot_status",
  "full_reindex_disabled",
];
const checks = new Map((evidence.checks || []).map((item) => [item.name, item]));
const missing = requiredChecks.filter((name) => checks.get(name)?.passed !== true);
const consoleErrors = evidence.console_errors || [];
const pageErrors = evidence.page_errors || [];
const networkFailures = evidence.unexpected_network_failures || [];

if (evidence.status !== "PASSED" || evidence.real_browser !== true || missing.length) {
  throw new Error(`U3 browser acceptance incomplete: ${missing.join(", ") || evidence.status}`);
}
if (consoleErrors.length || pageErrors.length || networkFailures.length) {
  throw new Error("U3 browser acceptance contains console, page, or unexpected network errors");
}
if (evidence.approval_submitted !== false) {
  throw new Error("U3 browser acceptance must not submit an approval");
}

console.log(JSON.stringify({
  status: "PASSED",
  evidence: path.relative(root, evidencePath).replaceAll("\\", "/"),
  checks: requiredChecks.length,
  real_browser: true,
  approval_submitted: false,
  console_errors: 0,
  page_errors: 0,
  unexpected_network_failures: 0,
}, null, 2));
