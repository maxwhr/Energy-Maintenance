import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outputDir = process.env.TASK25D_WRITE_OUTPUT_DIR || path.join(root, ".runtime", "task25d");
const outputPath = path.join(outputDir, "browser_review.json");
const credentialsPath = path.join(root, ".runtime", "task25a_r1", ".test_credentials.private.json");
const baseUrl = (process.env.TASK25D_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");
if (!fs.existsSync(credentialsPath)) throw new Error("private browser credentials are unavailable");
const credentials = JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
const browserPath = [
  process.env.TASK25D_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserPath) throw new Error("Chrome or Edge executable was not found");

const checks = {};
const consoleErrors = [];
const pageErrors = [];
const unexpectedNetworkFailures = [];
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
  await page.waitForTimeout(300);
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
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "failed";
    if (!reason.includes("ERR_ABORTED")) unexpectedNetworkFailures.push(`${request.method()} ${request.url()} ${reason}`);
  });
  page.on("response", (response) => {
    if (["fetch", "xhr"].includes(response.request().resourceType()) && response.status() >= 500) {
      unexpectedNetworkFailures.push(`${response.request().method()} ${response.url()} HTTP ${response.status()}`);
    }
  });

  const admin = await login(page, credentials.admin);
  record("admin_login", admin?.user?.role === "admin", admin?.user?.role);
  await page.goto(`${baseUrl}/maintenance-workflow`, { waitUntil: "networkidle" });
  await page.getByTestId("maintenance-workflow-page").waitFor({ state: "visible", timeout: 20000 });
  record("workbench_visible", await page.getByTestId("maintenance-workflow-page").isVisible());
  record("workflow_create_form", await page.getByTestId("workflow-create-form").isVisible());
  const status = await api(page, "/api/system/maintenance-workflow/status");
  record("quality_status_api", status.ok && status.data?.workflows >= 18, status.data?.workflows);
  const listItems = page.getByTestId("workflow-list-item");
  record("workflow_list", (await listItems.count()) >= 18, await listItems.count());
  await listItems.first().click();
  await page.getByTestId("workflow-stage-panel").waitFor({ state: "visible", timeout: 20000 });
  record("stage_stepper", await page.getByText("案例", { exact: true }).isVisible() && await page.getByText("纠错", { exact: true }).isVisible());
  record("case_evidence_panel", await page.getByText("案例、设备、媒体与证据", { exact: true }).isVisible());
  record("diagnosis_panel", await page.getByText("诊断草稿与人工确认", { exact: true }).isVisible());
  record("sop_panel", await page.getByText("SOP 草稿与审核", { exact: true }).isVisible());
  record("task_panel", await page.getByText("Task Draft 与正式任务创建", { exact: true }).isVisible());
  record("execution_panel", await page.getByText("任务执行、步骤与现场记录", { exact: true }).isVisible());
  record("verification_panel", await page.getByText("完成验证与显式关闭", { exact: true }).isVisible());
  record("correction_panel", await page.getByText("知识纠错候选", { exact: true }).isVisible());
  record("timeline_panel", await page.getByTestId("workflow-timeline").isVisible());
  const bodyText = await page.locator("body").innerText();
  record("disabled_reason_visible", bodyText.includes("不允许此操作") || bodyText.includes("unavailable during") || bodyText.includes("terminal workflow cannot be modified"));
  record("no_secret_rendered", !(await page.locator("body").innerText()).includes("DASHSCOPE_API_KEY") && !(await page.locator("body").innerText()).includes("Authorization: Bearer"));

  await page.evaluate(() => localStorage.clear());
  const viewer = await login(page, credentials.viewer);
  record("viewer_login", viewer?.user?.role === "viewer", viewer?.user?.role);
  await page.goto(`${baseUrl}/maintenance-workflow`, { waitUntil: "networkidle" });
  await page.getByTestId("maintenance-workflow-page").waitFor({ state: "visible", timeout: 20000 });
  record("viewer_write_actions_zero", await page.getByTestId("workflow-create-form").getByRole("button").isDisabled());

  await page.evaluate(() => localStorage.clear());
  const engineer = await login(page, credentials.engineer);
  record("engineer_login", engineer?.user?.role === "engineer", engineer?.user?.role);
  await page.goto(`${baseUrl}/maintenance-workflow`, { waitUntil: "networkidle" });
  await page.getByTestId("maintenance-workflow-page").waitFor({ state: "visible", timeout: 20000 });
  record("engineer_write_surface_enabled", !(await page.getByTestId("workflow-create-form").locator("input").first().isDisabled()));

  await page.evaluate(() => localStorage.clear());
  const expert = await login(page, credentials.expert);
  record("expert_login", expert?.user?.role === "expert", expert?.user?.role);
  await page.goto(`${baseUrl}/maintenance-workflow`, { waitUntil: "networkidle" });
  await page.getByTestId("maintenance-workflow-page").waitFor({ state: "visible", timeout: 20000 });
  const expertList = await api(page, "/api/maintenance-workflows?page=1&page_size=50");
  const expertItems = page.getByTestId("workflow-list-item");
  const expertUiCount = await expertItems.count();
  let expertPanelVisible = false;
  if (expertUiCount) {
    await expertItems.first().click();
    await page.getByTestId("workflow-stage-panel").waitFor({ state: "visible", timeout: 20000 });
    expertPanelVisible = await page.getByText("SOP 草稿与审核", { exact: true }).isVisible();
  }
  record(
    "expert_review_surface_visible",
    expertList.ok && Number(expertList.data?.total || 0) >= 18 && expertUiCount > 0 && expertPanelVisible,
    { apiTotal: expertList.data?.total || 0, uiCount: expertUiCount, panelVisible: expertPanelVisible },
  );

  record("console_errors_zero", consoleErrors.length === 0, consoleErrors);
  record("page_errors_zero", pageErrors.length === 0, pageErrors);
  record("unexpected_network_failures_zero", unexpectedNetworkFailures.length === 0, unexpectedNetworkFailures);
} finally {
  await browser.close();
}

const failed = Object.entries(checks).filter(([, value]) => !value.passed).map(([name]) => name);
const payload = {
  generated_at: new Date().toISOString(),
  status: failed.length ? "FAIL" : "PASS",
  checks,
  failed,
  console_errors: consoleErrors,
  page_errors: pageErrors,
  unexpected_network_failures: unexpectedNetworkFailures,
};
fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ status: payload.status, checks: Object.keys(checks).length, failed }, null, 2));
if (failed.length) process.exitCode = 1;
