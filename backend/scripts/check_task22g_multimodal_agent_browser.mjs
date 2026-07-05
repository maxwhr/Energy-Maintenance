import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE_URL = (process.env.TASK22G_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const API_BASE_URL = `${BASE_URL}/api`;
const ADMIN_USERNAME = process.env.TASK22G_ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.TASK22G_ADMIN_PASSWORD || "admin123456";
const VIEWER_USERNAME = process.env.TASK22G_VIEWER_USERNAME || `Task22G_viewer_${Date.now()}`;
const VIEWER_PASSWORD = process.env.TASK22G_VIEWER_PASSWORD || "Task22G_pass123";
const CDP_PORT = Number(process.env.TASK22G_CDP_PORT || 9227);
const RUN_ID = `Task22G_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const RUNTIME_DIR = path.resolve(process.cwd(), ".runtime", "task22g");
const RESULT_FILE = path.join(RUNTIME_DIR, "multimodal_agent_browser_result.json");
const SAMPLE_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

const browserCandidates = [
  process.env.TASK22G_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);

const results = [];
const consoleErrors = [];
const networkFailures = [];
let browserProcess;
let cdp;
let adminToken = "";
let mediaId = "";

function record(name, status, notes = "") {
  results.push({ name, status, notes });
  const marker = status === "passed" ? "[PASS]" : status === "blocked" ? "[BLOCKED]" : "[FAIL]";
  console.log(`${marker} ${name}${notes ? ` - ${notes}` : ""}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(fn, timeoutMs = 15000, intervalMs = 400) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }
  throw lastError || new Error(`Timeout after ${timeoutMs}ms`);
}

async function requestJson(method, pathOrUrl, { token = "", payload = undefined, timeoutMs = 20000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const url = pathOrUrl.startsWith("http") ? pathOrUrl : `${API_BASE_URL}${pathOrUrl}`;
    const response = await fetch(url, {
      method,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(payload !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: payload !== undefined ? JSON.stringify(payload) : undefined,
    });
    const text = await response.text();
    const body = text ? JSON.parse(text) : {};
    return { status: response.status, body };
  } finally {
    clearTimeout(timer);
  }
}

function apiData(label, response) {
  if (response.status >= 400 || ![0, 200].includes(response.body?.code)) {
    throw new Error(`${label} failed: http=${response.status}, code=${response.body?.code}, message=${response.body?.message}`);
  }
  return response.body.data;
}

async function login(username, password) {
  const data = apiData("login", await requestJson("POST", "/auth/login", { payload: { username, password } }));
  return data.access_token;
}

async function ensureViewer() {
  const query = new URLSearchParams({ keyword: VIEWER_USERNAME, page: "1", page_size: "20" });
  const page = apiData("list viewer", await requestJson("GET", `/users?${query}`, { token: adminToken }));
  const existing = (page.items || []).find((item) => item.username === VIEWER_USERNAME);
  if (existing) {
    await requestJson("PUT", `/users/${existing.id}`, {
      token: adminToken,
      payload: { password: VIEWER_PASSWORD, display_name: "Task22G Viewer", role: "viewer", status: "active" },
    });
    return;
  }
  apiData(
    "create viewer",
    await requestJson("POST", "/users", {
      token: adminToken,
      payload: { username: VIEWER_USERNAME, password: VIEWER_PASSWORD, display_name: "Task22G Viewer", role: "viewer", status: "active" },
    }),
  );
}

async function uploadMedia() {
  const form = new FormData();
  form.append("file", new Blob([SAMPLE_PNG], { type: "image/png" }), `${RUN_ID}_pv_inverter_alarm.png`);
  form.append("media_type", "fault_image");
  form.append("description", `${RUN_ID} browser selected PV inverter alarm screen`);
  form.append("manufacturer", "huawei");
  form.append("product_series", "SUN2000");
  form.append("device_type", "pv_inverter");
  form.append("fault_type", "low_insulation_resistance");
  form.append("alarm_code", `${RUN_ID}_ALARM`);
  const response = await fetch(`${API_BASE_URL}/media/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}`, Accept: "application/json" },
    body: form,
  });
  const body = await response.json();
  const data = apiData("upload media", { status: response.status, body });
  mediaId = data.media_id || data.id;
  if (!mediaId) throw new Error("media upload did not return media id");
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.ws.addEventListener("message", (event) => this.onMessage(event));
  }

  ready() {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("CDP websocket open timeout")), 10000);
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
  }

  onMessage(event) {
    const msg = JSON.parse(event.data);
    if (msg.id) {
      const entry = this.pending.get(msg.id);
      if (!entry) return;
      this.pending.delete(msg.id);
      if (msg.error) entry.reject(new Error(msg.error.message || "CDP error"));
      else entry.resolve(msg.result);
      return;
    }
    if (msg.method === "Runtime.consoleAPICalled" && ["error", "assert"].includes(msg.params?.type)) {
      consoleErrors.push((msg.params.args || []).map((arg) => arg.value || arg.description || "").join(" "));
    }
    if (msg.method === "Runtime.exceptionThrown") {
      consoleErrors.push(msg.params?.exceptionDetails?.exception?.description || "Runtime exception");
    }
    if (msg.method === "Network.loadingFailed" && !String(msg.params?.errorText || "").includes("net::ERR_ABORTED")) {
      networkFailures.push(msg.params?.errorText || "network failure");
    }
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Evaluation failed");
    }
    return result.result?.value;
  }

  async navigate(targetPath) {
    const url = targetPath.startsWith("http") ? targetPath : `${BASE_URL}${targetPath}`;
    await this.send("Page.navigate", { url });
    await waitFor(async () => ["complete", "interactive"].includes(await this.eval("document.readyState")), 15000);
    await sleep(900);
  }

  close() {
    try { this.ws.close(); } catch { /* noop */ }
  }
}

function domScript(body) {
  return `(() => {
    const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width >= 0 && rect.height >= 0;
    };
    const labelText = (el) => normalize(el.innerText || el.textContent || el.value || el.getAttribute("aria-label") || el.placeholder || "");
    const setValue = (el, value) => {
      if (!el) return false;
      el.focus();
      el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    };
    ${body}
  })()`;
}

async function bodyText() {
  return cdp.eval("document.body ? document.body.innerText : ''");
}

async function clickButton(text, timeoutMs = 15000) {
  await waitFor(() => cdp.eval(domScript(`
    const btn = Array.from(document.querySelectorAll("button,input[type='submit']")).filter(visible)
      .find((item) => !item.disabled && labelText(item).includes(${JSON.stringify(text)}));
    if (!btn) return false;
    btn.scrollIntoView({ block: "center", inline: "center" });
    btn.click();
    return true;
  `)), timeoutMs);
  await sleep(1200);
}

async function fillTextarea(value) {
  const ok = await cdp.eval(domScript(`
    const field = Array.from(document.querySelectorAll("textarea")).filter(visible)[0];
    return setValue(field, ${JSON.stringify(value)});
  `));
  if (!ok) throw new Error("textarea not found");
}

async function setMockRun(value) {
  await cdp.eval(domScript(`
    const labels = Array.from(document.querySelectorAll("label")).filter(visible);
    const holder = labels.find((item) => labelText(item).includes("mock-run"));
    const input = holder?.querySelector("input[type='checkbox']");
    if (!input || input.disabled) return false;
    input.checked = ${JSON.stringify(value)};
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  `));
  await sleep(400);
}

async function loginViaUi(username, password) {
  await cdp.navigate("/login");
  await cdp.eval(domScript(`
    const fields = Array.from(document.querySelectorAll("input")).filter(visible);
    setValue(fields.find((item) => item.type !== "password"), ${JSON.stringify(username)});
    setValue(fields.find((item) => item.type === "password"), ${JSON.stringify(password)});
    const submit = Array.from(document.querySelectorAll("form button[type='submit'], form input[type='submit']")).filter(visible)[0];
    submit?.click();
    return true;
  `));
  await waitFor(async () => {
    const text = await bodyText();
    const token = await cdp.eval("localStorage.getItem('energy_maintenance_access_token') || ''");
    return Boolean(token) && !text.includes("登录失败");
  }, 15000);
}

async function verifyRunDisplayed({ mock }) {
  await waitFor(async () => {
    const text = await bodyText();
    return text.includes("智能体运行结果") && text.includes("智能体执行时间线") && text.includes("智能体工具调用") && text.includes("安全复核清单");
  }, 30000);
  const text = await bodyText();
  if (!text.includes("external_api_called=false")) throw new Error("final_answer did not display external_api_called=false");
  if (mock && !text.toLowerCase().includes("mock")) throw new Error("mock-run result did not display mocked boundary");
  if (!mock && !text.toLowerCase().includes("blocked")) throw new Error("dry-run result did not display blocked boundary");
}

async function launchBrowser() {
  const browserPath = browserCandidates.find((candidate) => candidate && fs.existsSync(candidate));
  if (!browserPath) throw new Error("No Chrome or Edge executable found");
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "em-task22g-profile-"));
  browserProcess = spawn(browserPath, [
    "--headless=new",
    `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${userDataDir}`,
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "about:blank",
  ], { stdio: "ignore" });
  const pageTarget = await waitFor(async () => {
    try {
      const response = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`);
      if (!response.ok) return null;
      const targets = await response.json();
      return (targets || []).find((item) => item.type === "page" && item.webSocketDebuggerUrl);
    } catch {
      return null;
    }
  }, 15000);
  cdp = new CDPClient(pageTarget.webSocketDebuggerUrl);
  await cdp.ready();
  await cdp.send("Runtime.enable");
  await cdp.send("Page.enable");
  await cdp.send("DOM.enable");
  await cdp.send("Network.enable");
}

async function verifyAdminFlow() {
  await loginViaUi(ADMIN_USERNAME, ADMIN_PASSWORD);
  record("admin browser login", "passed");
  await cdp.navigate(`/multimodal?media_id=${encodeURIComponent(mediaId)}`);
  await waitFor(async () => (await bodyText()).includes("多模态证据中心"), 15000);
  record("open /multimodal", "passed", `media_id=${mediaId}`);

  await fillTextarea(`${RUN_ID} dry-run 多模态证据智能体：逆变器绝缘阻抗异常，确认 blocked/provider 边界。`);
  await setMockRun(false);
  await clickButton("创建多模态证据智能体运行");
  await verifyRunDisplayed({ mock: false });
  record("browser dry-run agent", "passed");

  await fillTextarea(`${RUN_ID} mock-run 多模态证据智能体：生成本地模拟 OCR 和 AI 证据，必须展示 mocked。`);
  await setMockRun(true);
  await clickButton("创建多模态证据智能体运行");
  await verifyRunDisplayed({ mock: true });
  record("browser mock-run agent", "passed");
}

async function verifyViewerReadonly() {
  await cdp.eval("localStorage.clear(); sessionStorage.clear(); true");
  await loginViaUi(VIEWER_USERNAME, VIEWER_PASSWORD);
  await cdp.navigate(`/multimodal?media_id=${encodeURIComponent(mediaId)}`);
  await waitFor(async () => (await bodyText()).includes("多模态证据中心"), 15000);
  const state = await cdp.eval(domScript(`
    const btn = Array.from(document.querySelectorAll("button")).filter(visible)
      .find((item) => labelText(item).includes("创建多模态证据智能体运行"));
    return btn ? Boolean(btn.disabled) : "missing";
  `));
  if (state !== true) throw new Error(`viewer create button should be disabled, got ${state}`);
  record("viewer readonly agent entry", "passed");
}

async function main() {
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  apiData("health", await requestJson("GET", "/health", { timeoutMs: 8000 }));
  adminToken = await login(ADMIN_USERNAME, ADMIN_PASSWORD);
  await ensureViewer();
  await uploadMedia();
  record("preflight API/media", "passed", `media_id=${mediaId}`);

  await launchBrowser();
  await verifyAdminFlow();
  await verifyViewerReadonly();

  const blockingErrors = consoleErrors.filter((item) => !String(item).includes("ResizeObserver loop"));
  if (blockingErrors.length) record("browser console errors", "failed", JSON.stringify(blockingErrors.slice(0, 5)));
  else record("browser console errors", "passed", "0");
  if (networkFailures.length) record("browser network failures", "failed", JSON.stringify(networkFailures.slice(0, 5)));
  else record("browser network failures", "passed", "0");
}

async function shutdown() {
  if (cdp) cdp.close();
  if (browserProcess) {
    try { browserProcess.kill(); } catch { /* noop */ }
  }
}

main()
  .catch((error) => {
    record("Task22G browser acceptance", "failed", error.stack || error.message);
  })
  .finally(async () => {
    await shutdown();
    fs.mkdirSync(RUNTIME_DIR, { recursive: true });
    fs.writeFileSync(
      RESULT_FILE,
      JSON.stringify({ base_url: BASE_URL, run_id: RUN_ID, media_id: mediaId, results, console_errors: consoleErrors, network_failures: networkFailures, no_package_generated: true }, null, 2),
      "utf8",
    );
    console.log(`RESULT_FILE=${RESULT_FILE}`);
    process.exit(results.some((item) => item.status === "failed") ? 1 : 0);
  });
