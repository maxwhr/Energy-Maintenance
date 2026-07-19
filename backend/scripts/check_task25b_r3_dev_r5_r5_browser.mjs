import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outputDir = path.join(root, ".runtime", "task25b_r3_dev_r5_r5");
const outputPath = path.join(outputDir, "browser_review.json");
const baseUrl = (process.env.TASK25B_R5_R5_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const adminUsername = requiredEnv("TASK25B_R5_R5_ADMIN_USERNAME");
const adminPassword = requiredEnv("TASK25B_R5_R5_ADMIN_PASSWORD");
const viewerUsername = requiredEnv("TASK25B_R5_R5_VIEWER_USERNAME");
const viewerPassword = requiredEnv("TASK25B_R5_R5_VIEWER_PASSWORD");
const browserPath = [
  process.env.TASK25B_R5_R5_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserPath) throw new Error("Chrome or Edge executable was not found");

const consoleErrors = [];
const pageErrors = [];
const unexpectedNetworkFailures = [];
const checks = {};
let adminLoginPayload = null;
let viewerLoginPayload = null;

function unwrap(payload) {
  return payload && typeof payload === "object" && "data" in payload ? payload.data : payload;
}

function record(name, passed, evidence = null) {
  checks[name] = { passed: Boolean(passed), evidence };
}

async function login(page, username, password) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.locator("input[autocomplete='username']").fill(username);
  await page.locator("input[type='password']").fill(password);
  const loginResponse = page.waitForResponse(
    (response) => response.url().includes("/api/auth/login") && response.request().method() === "POST",
    { timeout: 15000 },
  );
  await page.locator("form button[type='submit']").click();
  const response = await loginResponse;
  if (!response.ok()) throw new Error(`login failed with HTTP ${response.status()}`);
  const payload = unwrap(await response.json());
  if (!payload?.access_token || !payload?.user) {
    throw new Error("login business response did not contain an access token and user");
  }
  await page.waitForTimeout(500);
  if (new URL(page.url()).pathname.endsWith("/login")) {
    await page.evaluate(({ token, user }) => {
      localStorage.setItem("energy_maintenance_access_token", token);
      localStorage.setItem("user_info", JSON.stringify({
        id: user.id,
        username: user.username,
        displayName: user.display_name || user.username,
        role: user.role,
        roles: [user.role],
        status: user.status,
      }));
    }, { token: payload.access_token, user: payload.user });
    await page.goto(`${baseUrl}/dashboard`, { waitUntil: "networkidle" });
  }
  return payload;
}

async function submitQuery(page, query) {
  await page.getByTestId("query-aware-form").locator("textarea").fill(query);
  const apiResponse = page.waitForResponse(
    (response) => response.url().includes("/api/retrieval/query-aware-search") && response.request().method() === "POST",
    { timeout: 45000 },
  );
  await page.getByTestId("query-aware-form").locator("button[type='submit']").click();
  const response = await apiResponse;
  if (!response.ok()) throw new Error(`query-aware search failed with HTTP ${response.status()}`);
  const payload = unwrap(await response.json());
  await page.getByTestId("r5-r5-diagnostics").waitFor({ state: "visible", timeout: 45000 });
  return payload;
}

const browser = await chromium.launch({
  headless: true,
  executablePath: browserPath,
  args: ["--disable-gpu", "--no-first-run", "--no-default-browser-check"],
});

try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const errorText = request.failure()?.errorText || "failed";
    if (errorText.includes("ERR_ABORTED")) return;
    unexpectedNetworkFailures.push(`${request.method()} ${request.url()} ${errorText}`);
  });
  page.on("response", (response) => {
    if (["fetch", "xhr"].includes(response.request().resourceType()) && response.status() >= 400) {
      unexpectedNetworkFailures.push(`${response.request().method()} ${response.url()} HTTP ${response.status()}`);
    }
  });

  adminLoginPayload = await login(page, adminUsername, adminPassword);
  record("admin_login", adminLoginPayload?.user?.role === "admin", adminLoginPayload?.user?.role);

  await page.goto(`${baseUrl}/knowledge/search`, { waitUntil: "networkidle" });
  const composite = await submitQuery(
    page,
    "通信频繁中断，为什么会掉线，应该如何排查处理并确认已经恢复？",
  );
  const requested = new Set(composite.requested_information || []);
  const anchors = new Set(composite.retrieval_plan?.anchor_types || []);
  const variants = composite.retrieval_plan?.query_variants || [];
  const surfaced = composite.surfaced_results || [];

  record("primary_intent", composite.primary_intent === "TROUBLESHOOTING", composite.primary_intent);
  record("requested_information", requested.has("CAUSE") && requested.has("ACTION") && requested.has("VERIFICATION"), [...requested]);
  record("composite_intent", requested.size >= 2, requested.size);
  record("canonical_query", Boolean(composite.canonical_question?.trim()), composite.canonical_question);
  record("query_variants", variants.length >= 2 && variants.length <= 5 && variants[0]?.variant_type === "ORIGINAL", variants.map((item) => item.variant_type));
  record("anchor_coverage", anchors.has("CAUSE") && anchors.has("ACTION") && anchors.has("VERIFICATION"), [...anchors]);
  record("direct_answer_ranking", surfaced.length > 0 && typeof surfaced[0]?.direct_answer_score === "number", surfaced[0]?.direct_answer_level);
  record("multi_evidence_ranking", surfaced.length >= 2, surfaced.length);
  record("citation", (composite.citations || []).length > 0 && composite.citation_validity_ratio > 0, {
    citations: (composite.citations || []).length,
    validity: composite.citation_validity_ratio,
    coverage: composite.citation_coverage_ratio,
  });
  record("confidence", ["ANSWERABLE", "MULTIPLE_POSSIBILITIES"].includes(composite.confidence_status), composite.confidence_status);
  record("deterministic_only", composite.query_understanding_mode !== "MINIMAX_TOOL" && !composite.minimax_diagnostics?.called, composite.query_understanding_mode);
  record("ui_primary_intent", await page.getByTestId("primary-intent").isVisible());
  record("ui_requested_information", await page.getByTestId("requested-information").isVisible());
  record("ui_anchor_coverage", await page.getByTestId("anchor-coverage").isVisible());
  record("ui_direct_answer_ranking", await page.getByTestId("direct-answer-ranking").isVisible());
  record("ui_citation", await page.getByTestId("citation-panel").isVisible());

  const noAnswer = await submitQuery(
    page,
    "SUN2000-999KTL-X1 告警代码 990001 的原因和处理方法是什么？",
  );
  record("no_answer", noAnswer.confidence_status === "INSUFFICIENT_EVIDENCE", noAnswer.confidence_status);
  record("no_answer_boundary", Boolean(noAnswer.answer_boundary?.insufficient_evidence_notice));

  await page.evaluate(() => localStorage.clear());
  viewerLoginPayload = await login(page, viewerUsername, viewerPassword);
  record("viewer_login", viewerLoginPayload?.user?.role === "viewer", viewerLoginPayload?.user?.role);
  await page.goto(`${baseUrl}/system/retrieval-quality`, { waitUntil: "networkidle" });
  const r5Panel = page.getByTestId("r5-query-aware-status");
  await r5Panel.waitFor({ state: "visible", timeout: 20000 });
  record("viewer_quality_page", await r5Panel.isVisible());
  record("viewer_read_only", (await r5Panel.locator("button").count()) === 0, await r5Panel.locator("button").count());

  const html = await page.content();
  record(
    "no_secret_rendered",
    !html.includes(adminPassword) && !html.includes(viewerPassword) && !html.toLowerCase().includes("authorization: bearer"),
  );
  record("console_errors_zero", consoleErrors.length === 0, consoleErrors.length);
  record("page_errors_zero", pageErrors.length === 0, pageErrors.length);
  record("unexpected_network_failures_zero", unexpectedNetworkFailures.length === 0, unexpectedNetworkFailures.length);

  const failures = Object.entries(checks).filter(([, item]) => !item.passed).map(([name]) => name);
  const result = {
    generated_at: new Date().toISOString(),
    task: "Task 25B-R3-DEV-R5-R5 real Playwright browser review",
    status: failures.length ? "FAILED" : "PASSED",
    real_browser: true,
    automation: "project-node-playwright",
    base_url: baseUrl,
    browser_executable: path.basename(browserPath),
    checks,
    failures,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    unexpected_network_failures: unexpectedNetworkFailures,
  };
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: result.status, checks: Object.keys(checks).length, failures }));
  if (failures.length) process.exitCode = 2;
} finally {
  await browser.close();
}
