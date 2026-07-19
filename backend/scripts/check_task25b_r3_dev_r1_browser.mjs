import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..", "..");
const artifactPath = path.join(root, ".runtime", "task25b_r3_dev_r1", "browser.json");

if (!fs.existsSync(artifactPath)) {
  throw new Error(`browser evidence is missing: ${artifactPath}`);
}

const evidence = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
const requiredChecks = new Set([
  "scope_displayed",
  "actual_route_displayed",
  "chinese_filter_displayed",
  "v1_failure_preserved",
  "v2_result_separate",
  "benchmark_ready_separate_from_quality_gate",
  "viewer_read_only",
  "no_full_reindex_action",
  "no_secret_rendered",
]);
const observed = new Map((evidence.checks || []).map((item) => [item.name, item]));
const missing = [...requiredChecks].filter((name) => !observed.get(name)?.passed);
const failed = [
  ...missing.map((name) => `missing_or_failed:${name}`),
  ...(evidence.console_errors || []).map((value) => `console:${value}`),
  ...(evidence.page_errors || []).map((value) => `page:${value}`),
  ...(evidence.network_failures || []).map((value) => `network:${JSON.stringify(value)}`),
];

if (evidence.real_browser !== true) failed.push("real_browser:false");
if (evidence.approval_submitted !== false) failed.push("approval_boundary_violated");
if (evidence.pilot_indexed !== false) failed.push("pilot_index_boundary_violated");

const result = {
  status: failed.length ? "FAILED" : "PASSED",
  artifact: artifactPath,
  checks: observed.size,
  console_errors: (evidence.console_errors || []).length,
  page_errors: (evidence.page_errors || []).length,
  network_failures: (evidence.network_failures || []).length,
  failed,
};
console.log(JSON.stringify(result, null, 2));
if (failed.length) process.exitCode = 1;
