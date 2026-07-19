import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..", "..");
const evidencePath = path.join(root, ".runtime", "task25b_r2_u3_r3_dev", "browser.json");
if (!fs.existsSync(evidencePath)) throw new Error("R3-DEV in-app Browser evidence is missing");
const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const required = [
  "engineering_approval_badge", "not_human_expert_badge", "chinese_primary_visible",
  "english_alternate_visible", "viewer_read_only", "engineer_cannot_claim_expert",
  "pilot_only_visible", "secret_not_visible",
];
const checks = new Map((evidence.checks || []).map((item) => [item.name, item.passed]));
const missing = required.filter((name) => checks.get(name) !== true);
if (evidence.status !== "PASSED" || evidence.real_browser !== true || missing.length) {
  throw new Error(`R3-DEV browser acceptance incomplete: ${missing.join(", ")}`);
}
if ((evidence.console_errors || []).length || (evidence.page_errors || []).length || (evidence.unexpected_network_failures || []).length) {
  throw new Error("browser acceptance contains unexpected runtime errors");
}
console.log(JSON.stringify({status:"PASSED",checks:required.length,real_browser:true,
  console_errors:0,page_errors:0,unexpected_network_failures:0},null,2));
