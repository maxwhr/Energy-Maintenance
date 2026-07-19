import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outputDir = path.join(root, ".runtime", "task25b_r3_dev_r5_r6");
const outputPath = path.join(outputDir, "browser_review.json");
const credentialsPath = path.join(root, ".runtime", "task25a_r1", ".test_credentials.private.json");
const baseUrl = (process.env.TASK25B_R5_R6_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");
if (!fs.existsSync(credentialsPath)) throw new Error("private browser test credentials are not prepared");
const credentials = JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
const browserPath = [
  process.env.TASK25B_R5_R6_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserPath) throw new Error("Chrome or Edge executable was not found");

const checks = {};
const consoleErrors = [];
const pageErrors = [];
const networkFailures = [];
function record(name, passed, evidence = null) { checks[name] = { passed: Boolean(passed), evidence }; }
function unwrap(payload) { return payload && typeof payload === "object" && "data" in payload ? payload.data : payload; }

async function login(page, account) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.locator("input[autocomplete='username']").fill(account.username);
  await page.locator("input[type='password']").fill(account.password);
  const pending = page.waitForResponse((response) => response.url().includes("/api/auth/login") && response.request().method() === "POST");
  await page.locator("form button[type='submit']").click();
  const response = await pending;
  if (!response.ok()) throw new Error(`login failed with HTTP ${response.status()}`);
  const payload = unwrap(await response.json());
  await page.waitForTimeout(400);
  if (new URL(page.url()).pathname.endsWith("/login")) {
    await page.evaluate(({ token, user }) => {
      localStorage.setItem("energy_maintenance_access_token", token);
      localStorage.setItem("user_info", JSON.stringify({
        id: user.id, username: user.username, displayName: user.display_name || user.username,
        role: user.role, roles: [user.role], status: user.status,
      }));
    }, { token: payload.access_token, user: payload.user });
  }
  return payload;
}

const browser = await chromium.launch({ headless: true, executablePath: browserPath, args: ["--disable-gpu", "--no-first-run"] });
try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const message = request.failure()?.errorText || "failed";
    if (!message.includes("ERR_ABORTED")) networkFailures.push(`${request.method()} ${request.url()} ${message}`);
  });
  page.on("response", (response) => {
    if (["xhr", "fetch"].includes(response.request().resourceType()) && response.status() >= 400) {
      networkFailures.push(`${response.request().method()} ${response.url()} HTTP ${response.status()}`);
    }
  });

  const admin = await login(page, credentials.admin);
  record("admin_login", admin?.user?.role === "admin", admin?.user?.role);
  await page.goto(`${baseUrl}/knowledge/search`, { waitUntil: "networkidle" });
  await page.getByTestId("query-aware-form").locator("textarea").fill("通信频繁中断，原因是什么，应该如何处理并验证恢复？");
  const pending = page.waitForResponse(
    (response) => response.url().includes("/api/retrieval/query-aware-search") && response.request().method() === "POST",
    { timeout: 45000 },
  );
  await page.getByTestId("query-aware-form").locator("button[type='submit']").click();
  const response = await pending;
  const payload = unwrap(await response.json());
  await page.getByTestId("dedicated-rerank-diagnostics").waitFor({ state: "visible", timeout: 45000 });
  record("query_api", response.ok());
  record("dedicated_rerank_contract", Boolean(payload?.dedicated_rerank?.model), payload?.dedicated_rerank?.provider_status);
  record("config_missing_fallback_visible", payload?.dedicated_rerank?.fallback === true && payload?.dedicated_rerank?.fallback_reason === "QWEN3_RERANK_CONFIG_MISSING", payload?.dedicated_rerank?.fallback_reason);
  record("minimax_not_ranking", payload?.minimax_tiebreak?.called === false, payload?.minimax_tiebreak?.skipped_reason);
  record("candidate_boundary", payload?.diagnostics?.candidate_additions_by_rerank === 0 && payload?.diagnostics?.candidate_source_modifications_by_rerank === 0);
  record("rerank_ui", await page.getByTestId("dedicated-rerank-diagnostics").isVisible());

  await page.evaluate(() => localStorage.clear());
  const viewer = await login(page, credentials.viewer);
  record("viewer_login", viewer?.user?.role === "viewer", viewer?.user?.role);
  await page.goto(`${baseUrl}/system/retrieval-quality`, { waitUntil: "networkidle" });
  const panel = page.getByTestId("r5-r6-qwen-rerank-status");
  await panel.waitFor({ state: "visible", timeout: 20000 });
  record("quality_panel", await panel.isVisible());
  record("quality_panel_read_only", (await panel.locator("button").count()) === 0);
  const html = await page.content();
  record("no_secret_rendered", !html.includes(credentials.admin.password) && !html.includes(credentials.viewer.password) && !html.toLowerCase().includes("authorization: bearer"));
  record("no_full_candidate_internal_text", !html.includes("rerank_documents"));
  record("console_errors_zero", consoleErrors.length === 0, consoleErrors.length);
  record("page_errors_zero", pageErrors.length === 0, pageErrors.length);
  record("network_failures_zero", networkFailures.length === 0, networkFailures.length);

  const failures = Object.entries(checks).filter(([, value]) => !value.passed).map(([name]) => name);
  const result = {
    generated_at: new Date().toISOString(), task: "Task 25B-R3-DEV-R5-R6 browser review",
    status: failures.length ? "FAILED" : "PASSED", real_browser: true,
    automation: "project-node-playwright", base_url: baseUrl, browser_executable: path.basename(browserPath),
    checks, failures, console_errors: consoleErrors, page_errors: pageErrors, network_failures: networkFailures,
    credential_values_output: false, api_key_rendered: false, full_candidate_text_rendered: false,
  };
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: result.status, checks: Object.keys(checks).length, failures }));
  if (failures.length) process.exitCode = 2;
} finally {
  await browser.close();
}
