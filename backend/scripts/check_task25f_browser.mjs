import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outputDir = path.join(root, ".runtime", "task25f");
const outputPath = path.join(outputDir, "browser_review.json");
const credentialsPath = path.join(root, ".runtime", "task25a_r1", ".test_credentials.private.json");
const suitePath = path.join(outputDir, "performance_suite_manifest.json");
const baseUrl = (process.env.TASK25F_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");
if (!fs.existsSync(credentialsPath)) throw new Error("private browser credentials are unavailable");
if (!fs.existsSync(suitePath)) throw new Error("Task 25F suite manifest is unavailable");
const credentials = JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
const suite = JSON.parse(fs.readFileSync(suitePath, "utf8"));
const browserPath = [
  process.env.TASK25F_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserPath) throw new Error("Chrome or Edge executable was not found");

const checks = {};
const consoleErrors = [];
const pageErrors = [];
const unexpectedNetworkFailures = [];
const retrievalRequests = [];
let expectedAborts = 0;
function record(name, passed, evidence = null) { checks[name] = { passed: Boolean(passed), evidence }; }
function unwrap(payload) { return payload && typeof payload === "object" && "data" in payload ? payload.data : payload; }
function sha(value) { return crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex"); }
function suiteCase(tag) { return suite.rows.find((row) => (row.tags || []).includes(tag)); }

async function login(page, account) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.locator("input[autocomplete='username']").fill(account.username);
  await page.locator("input[type='password']").fill(account.password);
  const pending = page.waitForResponse((response) => response.url().includes("/api/auth/login") && response.request().method() === "POST");
  await page.locator("form button[type='submit']").click();
  const response = await pending;
  if (!response.ok()) throw new Error(`login failed: HTTP ${response.status()}`);
  const payload = unwrap(await response.json());
  await page.waitForTimeout(250);
  return payload;
}

async function api(page, apiPath) {
  return page.evaluate(async (apiPath) => {
    const token = localStorage.getItem("energy_maintenance_access_token") || "";
    const response = await fetch(apiPath, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    const payload = await response.json();
    return { ok: response.ok, status: response.status, data: payload?.data };
  }, apiPath);
}

async function search(page, query, mode = "auto") {
  const form = page.getByTestId("query-aware-form");
  await form.locator("textarea").fill(query);
  await form.locator("select").first().selectOption(mode);
  const pending = page.waitForResponse(
    (response) => response.url().includes("/api/retrieval/query-aware-search") && response.request().method() === "POST",
    { timeout: 60000 },
  );
  await form.locator("button[type='submit']").click();
  const response = await pending;
  const payload = unwrap(await response.json());
  await page.waitForTimeout(100);
  return { response, payload };
}

const exact = suiteCase("exact_alarm") || suiteCase("exact_model");
const hybrid = suiteCase("raw_vector");
const multi = suiteCase("composite_intent");
const clarification = suiteCase("requires_clarification");
const noAnswer = suiteCase("no_answer");

const browser = await chromium.launch({ headless: true, executablePath: browserPath, args: ["--disable-gpu", "--no-first-run"] });
try {
  const context = await browser.newContext({ viewport: { width: 1720, height: 1100 } });
  const page = await context.newPage();
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/retrieval/query-aware-search")) retrievalRequests.push({ method: request.method(), started_at: Date.now() });
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "failed";
    if (reason.includes("ERR_ABORTED") || reason.includes("ERR_FAILED")) {
      expectedAborts += 1;
      return;
    }
    unexpectedNetworkFailures.push(`${request.method()} ${new URL(request.url()).pathname} ${reason}`);
  });
  page.on("response", (response) => {
    const pathname = new URL(response.url()).pathname;
    if (["fetch", "xhr"].includes(response.request().resourceType()) && response.status() >= 500) {
      unexpectedNetworkFailures.push(`${response.request().method()} ${pathname} HTTP ${response.status()}`);
    }
  });

  const admin = await login(page, credentials.admin);
  record("admin_login", admin?.user?.role === "admin", admin?.user?.role);
  await page.goto(`${baseUrl}/knowledge/search`, { waitUntil: "networkidle" });
  await page.getByTestId("query-aware-form").waitFor({ state: "visible", timeout: 20000 });
  record("knowledge_search_page", await page.getByTestId("query-aware-form").isVisible());

  const exactStart = retrievalRequests.length;
  const exactFirst = await search(page, exact.query, "fast");
  record("exact_search", exactFirst.response.ok() && !exactFirst.payload?.needs_clarification, exact.query_hash);
  record("exact_search_single_request", retrievalRequests.length - exactStart === 1, retrievalRequests.length - exactStart);
  record("citation_visible", await page.getByTestId("citation-panel").isVisible() && (exactFirst.payload?.citations || []).length > 0, (exactFirst.payload?.citations || []).length);
  const exactOrder = sha((exactFirst.payload?.surfaced_results || []).map((item) => item.candidate_id));
  const exactSecond = await search(page, exact.query, "fast");
  record("stable_exact_result_order", sha((exactSecond.payload?.surfaced_results || []).map((item) => item.candidate_id)) === exactOrder, exactOrder);

  const hybridResult = await search(page, hybrid.query, "auto");
  record("hybrid_search", hybridResult.response.ok() && (hybridResult.payload?.requested_channels || []).includes("RAW_VECTOR"), hybrid.query_hash);
  const multiResult = await search(page, multi.query, "deep");
  record("multi_query_search", multiResult.response.ok() && (multiResult.payload?.generated_queries || []).length >= 3, (multiResult.payload?.generated_queries || []).length);
  const clarificationResult = await search(page, clarification.query, "auto");
  record("active_clarification", clarificationResult.payload?.needs_clarification === true && await page.getByTestId("clarification-panel").isVisible(), clarification.query_hash);
  const noAnswerResult = await search(page, noAnswer.query, "auto");
  record("no_answer_boundary", noAnswerResult.response.ok() && ["INSUFFICIENT_EVIDENCE", "NEEDS_CLARIFICATION"].includes(noAnswerResult.payload?.confidence_status), noAnswer.query_hash);

  const duplicateStart = retrievalRequests.length;
  const form = page.getByTestId("query-aware-form");
  await form.locator("textarea").fill(exact.query);
  await form.locator("select").first().selectOption("fast");
  await form.evaluate((element) => element.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  await form.evaluate((element) => element.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  await page.waitForResponse((response) => response.url().includes("/api/retrieval/query-aware-search") && response.request().method() === "POST", { timeout: 30000 });
  await page.waitForTimeout(300);
  record("debounce_and_same_inflight_dedup", retrievalRequests.length - duplicateStart === 1, retrievalRequests.length - duplicateStart);

  const cancelStart = retrievalRequests.length;
  await form.locator("textarea").fill(hybrid.query);
  await form.locator("select").first().selectOption("auto");
  await form.evaluate((element) => element.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  await page.waitForRequest((request) => request.url().includes("/api/retrieval/query-aware-search"), { timeout: 10000 });
  await form.locator("textarea").fill(exact.query);
  await form.locator("select").first().selectOption("fast");
  await form.evaluate((element) => element.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  await page.waitForResponse((response) => response.url().includes("/api/retrieval/query-aware-search") && response.request().method() === "POST" && response.ok(), { timeout: 60000 });
  await page.waitForTimeout(300);
  record("old_request_cancelled", retrievalRequests.length - cancelStart === 2 && expectedAborts >= 1, { requests: retrievalRequests.length - cancelStart, expected_aborts: expectedAborts });

  await form.locator("textarea").fill(hybrid.query);
  await form.locator("select").first().selectOption("auto");
  await form.evaluate((element) => element.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  await page.waitForRequest((request) => request.url().includes("/api/retrieval/query-aware-search"), { timeout: 10000 });
  await page.goto(`${baseUrl}/system/retrieval-quality`, { waitUntil: "networkidle" });
  record("page_leave_cancels_request", expectedAborts >= 2, expectedAborts);
  await page.getByTestId("rag-performance-summary").waitFor({ state: "visible", timeout: 20000 });
  const performanceApi = await api(page, "/api/system/retrieval-performance/summary");
  record("admin_sanitized_performance_summary", performanceApi.ok && await page.getByTestId("rag-performance-summary").isVisible(), performanceApi.status);
  record("performance_summary_has_no_query_text", !JSON.stringify(performanceApi.data || {}).includes(exact.query), null);

  await page.evaluate(() => localStorage.clear());
  const viewer = await login(page, credentials.viewer);
  record("viewer_login", viewer?.user?.role === "viewer", viewer?.user?.role);
  await page.goto(`${baseUrl}/system/retrieval-quality`, { waitUntil: "networkidle" });
  record("viewer_trace_panel_hidden", await page.getByTestId("rag-performance-summary").count() === 0);
  const viewerPerformance = await api(page, "/api/system/retrieval-performance/summary");
  record("viewer_performance_api_denied", viewerPerformance.status === 403, viewerPerformance.status);
  await page.goto(`${baseUrl}/knowledge/search`, { waitUntil: "networkidle" });
  const viewerHtml = await page.content();
  record("ordinary_user_no_internal_trace", !viewerHtml.includes("sql_total_ms") && !viewerHtml.includes("provider_total_ms"));

  const unexpectedConsoleErrors = consoleErrors.filter((message) =>
    !message.includes("403 (Forbidden)")
  );
  record("console_errors_zero", unexpectedConsoleErrors.length === 0, unexpectedConsoleErrors);
  record("page_errors_zero", pageErrors.length === 0, pageErrors);
  record("unexpected_network_failures_zero", unexpectedNetworkFailures.length === 0, unexpectedNetworkFailures);
} finally {
  await browser.close();
}

const failed = Object.entries(checks).filter(([, value]) => !value.passed).map(([name]) => name);
const payload = {
  generated_at: new Date().toISOString(),
  status: failed.length ? "FAIL" : "PASS",
  real_browser: true,
  automation: "project-node-playwright",
  app_browser_runtime: "BLOCKED_CANNOT_REDEFINE_PROCESS",
  fallback_reason: "The mandatory browser skill runtime could not initialize; standalone project Playwright was used.",
  base_url: baseUrl,
  browser_executable: path.basename(browserPath),
  checks,
  failed,
  query_text_recorded: false,
  retrieval_request_count: retrievalRequests.length,
  expected_abort_count: expectedAborts,
  console_errors: consoleErrors,
  expected_console_errors: consoleErrors.filter((message) => message.includes("403 (Forbidden)")),
  page_errors: pageErrors,
  unexpected_network_failures: unexpectedNetworkFailures,
};
fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ status: payload.status, checks: Object.keys(checks).length, failed, expected_abort_count: expectedAborts }));
if (failed.length) process.exitCode = 1;
