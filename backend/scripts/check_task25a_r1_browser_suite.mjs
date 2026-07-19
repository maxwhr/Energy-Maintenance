import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const BACKEND = path.resolve(SCRIPT_DIR, "..");
const ROOT = path.resolve(BACKEND, "..");
const RUNTIME = path.join(ROOT, ".runtime", "task25a_r1");
const DOC = path.join(ROOT, "docs", "25A_R1_browser_acceptance_report.md");
const PRIVATE_CREDENTIALS = path.join(RUNTIME, ".test_credentials.private.json");
const BASE_URL = (process.env.TASK25A_R1_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
fs.mkdirSync(RUNTIME, { recursive: true });

const now = () => new Date().toISOString();
const rel = (value) => path.relative(ROOT, value).replaceAll("\\", "/");
const sha256 = (value) => fs.existsSync(value) && fs.statSync(value).isFile()
  ? crypto.createHash("sha256").update(fs.readFileSync(value)).digest("hex")
  : null;
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");

function loadCredentials() {
  if (!fs.existsSync(PRIVATE_CREDENTIALS)) {
    throw new Error("Private secure Task 25A-R1 test credential configuration is required");
  }
  const payload = JSON.parse(fs.readFileSync(PRIVATE_CREDENTIALS, "utf8"));
  for (const role of ["admin", "expert", "engineer", "viewer"]) {
    if (!payload[role]?.username || !payload[role]?.password) throw new Error(`secure credential role missing: ${role}`);
  }
  return payload;
}

function discover(dir) {
  if (!fs.existsSync(dir)) return [];
  const matches = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) matches.push(...discover(full));
    else if (entry.name.endsWith(".mjs") && /(browser|click|ui|playwright)/i.test(entry.name) && entry.name !== "check_task25a_r1_browser_suite.mjs") matches.push(full);
  }
  return matches;
}

const resultFiles = {
  check_task21c_browser_clicks: path.join(ROOT, ".runtime", "task21c", "browser_click_result.json"),
  check_task22f_multimodal_frontend_browser: path.join(ROOT, ".runtime", "task22f", "multimodal_frontend_browser_result.json"),
  check_task22g_multimodal_agent_browser: path.join(ROOT, ".runtime", "task22g", "multimodal_agent_browser_result.json"),
  check_task22h_diagnosis_sop_task_agent_browser: path.join(ROOT, ".runtime", "task22h", "diagnosis_sop_task_agent_browser_result.json"),
  check_task22i_knowledge_curator_agent_browser: path.join(ROOT, ".runtime", "task22i", "knowledge_curator_agent_browser_result.json"),
  check_task22j_artifact_conversion_browser: path.join(ROOT, ".runtime", "task22j", "artifact_conversion_browser_result.json"),
  check_task24e_conversion_history_browser: path.join(ROOT, ".runtime", "task24e", "conversion_history_browser_result.json"),
};

const pageCoverage = {
  check_task21c_browser_clicks: ["login", "Dashboard", "devices", "knowledge documents", "knowledge retrieval", "diagnosis", "SOP", "tasks/work orders", "Record Center", "knowledge graph", "system status", "RBAC viewer read-only"],
  check_task22f_multimodal_frontend_browser: ["multimodal evidence center", "Agent Workbench", "RBAC viewer read-only"],
  check_task22g_multimodal_agent_browser: ["multimodal evidence center", "Agent Workbench"],
  check_task22h_diagnosis_sop_task_agent_browser: ["diagnosis", "SOP", "tasks/work orders", "Agent Workbench"],
  check_task22i_knowledge_curator_agent_browser: ["knowledge documents", "knowledge contribution", "Agent Workbench"],
  check_task22j_artifact_conversion_browser: ["Agent Workbench", "artifact conversion"],
  check_task24e_conversion_history_browser: ["conversion history", "Agent Workbench"],
};

function prefixFor(scriptName) {
  const match = scriptName.match(/check_(task\d+[a-z]?)/i);
  return match ? match[1].toUpperCase() : null;
}

function childEnvironment(script, credentials, port) {
  const base = path.basename(script, ".mjs");
  const prefix = prefixFor(base);
  if (!prefix) throw new Error(`cannot determine environment prefix for ${base}`);
  const env = {
    ...process.env,
    TASK25A_R1_DATA_PREFIX: "Task25AR1_",
    [`${prefix}_BASE_URL`]: BASE_URL,
    [`${prefix}_CDP_PORT`]: String(port),
    [`${prefix}_ADMIN_USERNAME`]: credentials.admin.username,
    [`${prefix}_ADMIN_PASSWORD`]: credentials.admin.password,
    [`${prefix}_EXPERT_USERNAME`]: credentials.expert.username,
    [`${prefix}_EXPERT_PASSWORD`]: credentials.expert.password,
    [`${prefix}_ENGINEER_USERNAME`]: credentials.engineer.username,
    [`${prefix}_ENGINEER_PASSWORD`]: credentials.engineer.password,
    [`${prefix}_VIEWER_USERNAME`]: credentials.viewer.username,
    [`${prefix}_VIEWER_PASSWORD`]: credentials.viewer.password,
    CLOUD_LLM_REAL_CALL_ENABLED: "false",
    MIMO_REAL_CALL_ENABLED: "false",
    OCR_API_REAL_CALL_ENABLED: "false",
    DASHVECTOR_REAL_CALL_ENABLED: "false",
    EMBEDDING_REAL_CALL_ENABLED: "false",
  };
  return env;
}

function execute(script, env, cwd, logFile) {
  return new Promise((resolve) => {
    const startedAt = now();
    const started = performance.now();
    const child = spawn(process.execPath, [script], { cwd, env, windowsHide: true });
    const chunks = [];
    const errors = [];
    child.stdout.on("data", (data) => chunks.push(data));
    child.stderr.on("data", (data) => errors.push(data));
    child.on("error", (error) => errors.push(Buffer.from(`${error.name}: ${error.message}`)));
    child.on("close", (code) => {
      const stdout = Buffer.concat(chunks).toString("utf8");
      const stderr = Buffer.concat(errors).toString("utf8");
      fs.writeFileSync(logFile, `${stdout}\n${stderr}`, "utf8");
      resolve({ started_at: startedAt, completed_at: now(), duration_seconds: Number(((performance.now() - started) / 1000).toFixed(3)), exit_code: code ?? 1, stdout, stderr });
    });
  });
}

function safeResult(file) {
  if (!fs.existsSync(file)) return null;
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return null; }
}

function mergeTestRegistry(testResult, artifactPaths) {
  const file = path.join(RUNTIME, "test_execution_registry.json");
  const payload = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : { generated_at: now(), tests: [] };
  const entry = {
    test_id: "T-R1-BROWSER-SUITE",
    name: "All applicable browser scripts",
    category: "browser",
    command: "node backend/scripts/check_task25a_r1_browser_suite.mjs",
    started_at: testResult.started_at,
    completed_at: testResult.completed_at,
    duration_seconds: testResult.duration_seconds,
    environment: { os: process.platform, architecture: process.arch, browser_transport: "installed Edge/Chrome CDP", external_provider_mode: "disabled_for_task25a_r1" },
    api_base_url: BASE_URL,
    database_host: "127.0.0.1",
    database_port: 55432,
    real_external_api_used: false,
    mocked: true,
    exit_code: testResult.exit_code,
    status: testResult.exit_code === 0 ? "PASSED" : "FAILED",
    assertion_count: testResult.assertion_count,
    passed_assertions: testResult.passed_assertions,
    failed_assertions: testResult.failed_assertions,
    artifact_paths: artifactPaths.filter(fs.existsSync).map(rel),
    artifact_hashes: Object.fromEntries(artifactPaths.filter(fs.existsSync).map((item) => [rel(item), sha256(item)])),
    notes: "Console, page, network and unexpected HTTP failures are aggregated; any child failure makes the suite fail. Real providers remained disabled.",
  };
  payload.tests = [...(payload.tests || []).filter((item) => item.test_id !== entry.test_id), entry].sort((a, b) => a.test_id.localeCompare(b.test_id));
  payload.generated_at = now();
  writeJson(file, payload);
}

async function main() {
  const suiteStartedAt = now();
  const suiteStarted = performance.now();
  const credentials = loadCredentials();
  const failedOnly = process.argv.includes("--failed-only");
  const previousResultsPath = path.join(RUNTIME, "browser_test_results.json");
  const previousRows = failedOnly && fs.existsSync(previousResultsPath)
    ? (JSON.parse(fs.readFileSync(previousResultsPath, "utf8")).results || [])
    : [];
  const previousByName = new Map(previousRows.map((item) => [item.name, item]));
  const discovered = [...new Set([...discover(SCRIPT_DIR), ...discover(path.join(ROOT, "scripts"))])].sort();
  const inventory = discovered.map((script, index) => {
    const name = path.basename(script, ".mjs");
    return { script: rel(script), name, applicable: Object.hasOwn(resultFiles, name), command: `node ${rel(script)}`, pages: pageCoverage[name] || [], cdp_port: 9240 + index };
  });
  const inventoryPath = path.join(RUNTIME, "browser_test_inventory.json");
  writeJson(inventoryPath, { generated_at: now(), discovery_patterns: ["backend/scripts/*browser*.mjs", "backend/scripts/*click*.mjs", "backend/scripts/*ui*.mjs", "backend/scripts/*playwright*.mjs", "scripts/*browser*.mjs"], inventory });

  const results = [];
  const allConsoleErrors = [];
  const allPageErrors = [];
  const allNetworkFailures = [];
  let applicableSinceCooldown = 0;
  for (const [index, item] of inventory.entries()) {
    if (!item.applicable) {
      results.push({ ...item, status: "SKIPPED", reason: "discovered but no compatible result adapter", started_at: now(), completed_at: now(), duration_seconds: 0, exit_code: null, console_errors: [], page_errors: [], network_failures: [], unexpected_http_failures: [], artifact_paths: [], creates_test_data: false, test_data_prefix: "Task25AR1_" });
      continue;
    }
    if (failedOnly && previousByName.get(item.name)?.status === "PASSED") {
      results.push({ ...previousByName.get(item.name), reused_current_run_result: true });
      continue;
    }
    if (applicableSinceCooldown >= 2) {
      console.log("browser_rate_limit_cooldown phase=1 seconds=31");
      await new Promise((resolve) => setTimeout(resolve, 31000));
      console.log("browser_rate_limit_cooldown phase=2 seconds=31");
      await new Promise((resolve) => setTimeout(resolve, 31000));
      applicableSinceCooldown = 0;
    }
    console.log(`browser_child_start name=${item.name}`);
    const script = path.join(ROOT, item.script);
    const logFile = path.join(RUNTIME, `browser_${item.name}.log`);
    const legacyCwd = ["check_task21c_browser_clicks", "check_task22f_multimodal_frontend_browser"].includes(item.name) ? BACKEND : ROOT;
    const execution = await execute(script, childEnvironment(script, credentials, 9240 + index), legacyCwd, logFile);
    const artifact = resultFiles[item.name];
    const childResult = safeResult(artifact) || {};
    const consoleErrors = Array.isArray(childResult.console_errors) ? childResult.console_errors : [];
    const pageErrors = Array.isArray(childResult.page_errors) ? childResult.page_errors : [];
    const networkFailures = Array.isArray(childResult.network_failures) ? childResult.network_failures : [];
    const unexpected = networkFailures.filter((failure) => /\b(?:4\d\d|5\d\d)\b/.test(JSON.stringify(failure)) && !/\b(?:401|403|404)\b/.test(JSON.stringify(failure)));
    const assertionRows = Array.isArray(childResult.results) ? childResult.results : [];
    const failedAssertions = assertionRows.filter((row) => String(row.status).toLowerCase() === "failed").length;
    const blocked = execution.exit_code !== 0 && /browser executable|external service.*(?:missing|unavailable)/i.test(execution.stderr);
    const status = execution.exit_code === 0 && failedAssertions === 0 ? "PASSED" : (blocked ? "BLOCKED" : "FAILED");
    const row = {
      ...item, ...execution, status,
      assertion_count: assertionRows.length,
      passed_assertions: assertionRows.filter((value) => String(value.status).toLowerCase() === "passed").length,
      failed_assertions: failedAssertions,
      console_errors: consoleErrors, page_errors: pageErrors, network_failures: networkFailures, unexpected_http_failures: unexpected,
      artifact_paths: [artifact, logFile].filter(fs.existsSync).map(rel), screenshot_paths: (childResult.screenshots || []).map(String),
      creates_test_data: true, test_data_prefix: "Task25AR1_", real_external_api_used: false,
      viewer_rbac: item.pages.includes("RBAC viewer read-only"), admin_flow: true,
    };
    results.push(row);
    applicableSinceCooldown += 1;
    console.log(`browser_child_complete name=${item.name} status=${status} exit=${execution.exit_code}`);
    allConsoleErrors.push(...consoleErrors.map((value) => ({ script: item.name, value })));
    allPageErrors.push(...pageErrors.map((value) => ({ script: item.name, value })));
    allNetworkFailures.push(...networkFailures.map((value) => ({ script: item.name, value })));
  }

  const counts = Object.fromEntries(["PASSED", "FAILED", "BLOCKED", "SKIPPED"].map((status) => [status.toLowerCase(), results.filter((item) => item.status === status).length]));
  const summary = {
    discovered: inventory.length, executed: results.filter((item) => !["SKIPPED"].includes(item.status)).length,
    ...counts, console_errors: allConsoleErrors.length, page_errors: allPageErrors.length, network_failures: allNetworkFailures.length,
    unexpected_http_failures: results.reduce((sum, item) => sum + item.unexpected_http_failures.length, 0),
    viewer_rbac: results.some((item) => item.viewer_rbac && item.status === "PASSED") ? "PASSED" : "FAILED",
    admin_flows: results.some((item) => item.admin_flow && item.status === "PASSED") ? "PASSED" : "FAILED",
    real_external_api_used: false,
  };
  const resultPath = path.join(RUNTIME, "browser_test_results.json");
  const consolePath = path.join(RUNTIME, "browser_console_errors.json");
  const networkPath = path.join(RUNTIME, "browser_network_failures.json");
  writeJson(resultPath, { generated_at: now(), base_url: BASE_URL, summary, results });
  writeJson(consolePath, { generated_at: now(), console_errors: allConsoleErrors, page_errors: allPageErrors });
  writeJson(networkPath, { generated_at: now(), network_failures: allNetworkFailures, unexpected_http_failures: results.flatMap((item) => item.unexpected_http_failures.map((value) => ({ script: item.name, value }))) });

  const lines = [
    "# Task 25A-R1 浏览器验收报告", "", `生成时间：${now()}`, "",
    "## 汇总", "", `- discovered=${summary.discovered}；executed=${summary.executed}；passed=${summary.passed}；failed=${summary.failed}；blocked=${summary.blocked}；skipped=${summary.skipped}。`,
    `- console errors=${summary.console_errors}；page errors=${summary.page_errors}；network failures=${summary.network_failures}；unexpected 4xx/5xx=${summary.unexpected_http_failures}。`,
    `- viewer RBAC=${summary.viewer_rbac}；admin flows=${summary.admin_flows}；real external API used=false。`,
    "- 所有脚本使用 `Task25AR1_` 数据前缀；任何 child failure 都会令 suite 非零，build 成功不会覆盖浏览器失败。", "",
    "## 脚本结果", "", "| 脚本 | 状态 | 时长(s) | 断言 | console/page/network | 页面 |", "|---|---|---:|---:|---|---|",
    ...results.map((item) => `| \`${item.script}\` | ${item.status} | ${item.duration_seconds} | ${item.passed_assertions || 0}/${item.assertion_count || 0} | ${item.console_errors.length}/${item.page_errors.length}/${item.network_failures.length} | ${(item.pages || []).join("、")} |`),
    "", "## 边界", "", "- 本轮验证登录、Dashboard、设备、知识、检索、诊断、SOP、任务、记录中心、多模态、Agent、转换历史、知识图谱、系统状态与 viewer 只读边界。",
    "- dry-run/mock 场景仍标记为 mock；provider real-run 只验证权限/状态，未发起真实外部调用。", "",
  ];
  fs.writeFileSync(DOC, lines.join("\n"), "utf8");
  const exitCode = summary.failed || summary.blocked || summary.skipped || summary.viewer_rbac !== "PASSED" || summary.admin_flows !== "PASSED" ? 1 : 0;
  const artifactPaths = [inventoryPath, resultPath, consolePath, networkPath, DOC, ...results.flatMap((item) => item.artifact_paths.map((value) => path.join(ROOT, value)))];
  mergeTestRegistry({
    started_at: suiteStartedAt, completed_at: now(), duration_seconds: Number(((performance.now() - suiteStarted) / 1000).toFixed(3)), exit_code: exitCode,
    assertion_count: results.reduce((sum, item) => sum + (item.assertion_count || 0), 0),
    passed_assertions: results.reduce((sum, item) => sum + (item.passed_assertions || 0), 0),
    failed_assertions: results.reduce((sum, item) => sum + (item.failed_assertions || 0), 0) + summary.failed + summary.blocked + summary.skipped,
  }, artifactPaths);
  console.log(`task25a_r1_browser_suite discovered=${summary.discovered} passed=${summary.passed} failed=${summary.failed} blocked=${summary.blocked} skipped=${summary.skipped}`);
  process.exitCode = exitCode;
}

main().catch((error) => {
  const failure = { generated_at: now(), summary: { discovered: 0, executed: 0, passed: 0, failed: 1, blocked: 0, skipped: 0 }, error: `${error.name}: ${error.message}` };
  writeJson(path.join(RUNTIME, "browser_test_results.json"), failure);
  console.error(failure.error);
  process.exitCode = 1;
});
