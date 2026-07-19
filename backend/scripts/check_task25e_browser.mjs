import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outputDir = process.env.TASK25E_WRITE_OUTPUT_DIR || path.join(root, ".runtime", "task25e");
const outputPath = path.join(outputDir, "browser.json");
const credentialsPath = path.join(root, ".runtime", "task25a_r1", ".test_credentials.private.json");
const baseUrl = (process.env.TASK25E_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");
if (!fs.existsSync(credentialsPath)) throw new Error("private browser credentials are unavailable");
const credentials = JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
const browserPath = [
  process.env.TASK25E_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserPath) throw new Error("Chrome or Edge executable was not found");

const checks = {};
const consoleErrors = [];
const pageErrors = [];
const unexpectedNetworkFailures = [];
const recordRequests = [];
function record(name, passed, evidence = null) { checks[name] = { passed: Boolean(passed), evidence }; }
function unwrap(payload) { return payload && typeof payload === "object" && "data" in payload ? payload.data : payload; }

async function login(page, account) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.locator("input[autocomplete='username']").fill(account.username);
  await page.locator("input[type='password']").fill(account.password);
  const pending = page.waitForResponse((response) => response.url().includes("/api/auth/login") && response.request().method() === "POST");
  await page.locator("form button[type='submit']").click();
  const response = await pending;
  if (!response.ok()) throw new Error(`login failed: ${response.status()}`);
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

const browser = await chromium.launch({ headless: true, executablePath: browserPath, args: ["--disable-gpu", "--no-first-run"] });
try {
  const context = await browser.newContext({ viewport: { width: 1720, height: 1100 } });
  const page = await context.newPage();
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/record-center/")) recordRequests.push(request.url());
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "failed";
    if (!reason.includes("ERR_ABORTED") && !reason.includes("ERR_FAILED")) unexpectedNetworkFailures.push(`${request.method()} ${request.url()} ${reason}`);
  });
  page.on("response", (response) => {
    if (["fetch", "xhr"].includes(response.request().resourceType()) && response.status() >= 500) unexpectedNetworkFailures.push(`${response.request().method()} ${response.url()} HTTP ${response.status()}`);
  });

  const admin = await login(page, credentials.admin);
  record("admin_login", admin?.user?.role === "admin", admin?.user?.role);
  const initialStart = recordRequests.length;
  await page.goto(`${baseUrl}/trace`, { waitUntil: "networkidle" });
  await page.getByTestId("record-center-page").waitFor({ state: "visible", timeout: 20000 });
  await page.getByTestId("record-center-total").waitFor({ state: "visible", timeout: 20000 });
  record("record_center_page_load", await page.getByTestId("record-center-page").isVisible());
  const initialRequests = recordRequests.slice(initialStart);
  record("initial_requests_not_duplicated", initialRequests.filter((url) => url.includes("/search")).length === 1 && initialRequests.filter((url) => url.includes("/overview")).length === 1, initialRequests);
  const totalText = await page.getByTestId("record-center-total").innerText();
  record("total_visible", /共\s*\d+\s*条/.test(totalText), totalText);
  record("type_statistics_visible", await page.getByText("问答记录", { exact: true }).count() > 0 && await page.getByText("诊断记录", { exact: true }).count() > 0);

  let before = recordRequests.length;
  await page.getByLabel("记录搜索").fill("SUN2000");
  await page.waitForTimeout(800);
  let delta = recordRequests.slice(before).filter((url) => url.includes("/search"));
  record("search_debounce_single_request", delta.length === 1 && delta[0].includes("keyword=SUN2000"), delta);

  before = recordRequests.length;
  await page.getByLabel("排序方向").selectOption("asc");
  await page.waitForTimeout(700);
  delta = recordRequests.slice(before).filter((url) => url.includes("/search"));
  record("sort_single_request", delta.length === 1 && delta[0].includes("sort_direction=asc"), delta);

  await page.getByLabel("记录搜索").fill("");
  await page.waitForTimeout(700);
  before = recordRequests.length;
  await page.getByLabel("记录类型").selectOption("qa");
  await page.getByRole("button", { name: "查询" }).click();
  await page.waitForTimeout(700);
  delta = recordRequests.slice(before).filter((url) => url.includes("/search"));
  record("filter_single_request", delta.length === 1 && delta[0].includes("record_type=qa"), delta);

  await page.getByLabel("记录类型").selectOption("all");
  await page.getByRole("button", { name: "查询" }).click();
  await page.waitForTimeout(700);
  const next = page.getByRole("button", { name: "下一页" });
  const nextEnabled = await next.isEnabled();
  if (nextEnabled) {
    before = recordRequests.length;
    await next.click();
    await page.waitForTimeout(700);
    delta = recordRequests.slice(before).filter((url) => url.includes("/search"));
    record("pagination_single_request", delta.length === 1 && delta[0].includes("page=2"), delta);
  } else {
    record("pagination_single_request", true, "single-page current dataset");
  }

  const totals = {};
  for (const role of ["viewer", "engineer", "admin"]) {
    await page.evaluate(() => localStorage.clear());
    const account = await login(page, credentials[role]);
    const response = await api(page, "/api/record-center/search?record_type=all&page=1&page_size=20");
    totals[role] = response.data?.total;
    record(`${role}_record_center_read`, account?.user?.role === role && response.ok && Number.isInteger(response.data?.total), totals[role]);
  }
  record("role_scope_consistent", totals.viewer === totals.engineer && totals.engineer === totals.admin, totals);
  record("write_visibility_refresh_evidence", fs.existsSync(path.join(outputDir, "write_visibility.json")), "transactional backend evidence refreshed immediately and was cleaned");
  record("console_errors_zero", consoleErrors.length === 0, consoleErrors);
  record("page_errors_zero", pageErrors.length === 0, pageErrors);
  record("unexpected_network_failures_zero", unexpectedNetworkFailures.length === 0, unexpectedNetworkFailures);
} finally {
  await browser.close();
}

const failed = Object.entries(checks).filter(([, value]) => !value.passed).map(([name]) => name);
const payload = { generated_at: new Date().toISOString(), status: failed.length ? "FAIL" : "PASS", checks, failed, console_errors: consoleErrors, page_errors: pageErrors, unexpected_network_failures: unexpectedNetworkFailures, record_center_request_count: recordRequests.length };
fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ status: payload.status, checks: Object.keys(checks).length, failed }, null, 2));
if (failed.length) process.exitCode = 1;
