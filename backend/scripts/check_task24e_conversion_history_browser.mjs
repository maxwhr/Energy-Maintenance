import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE_URL = (process.env.TASK24E_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const API_BASE_URL = `${BASE_URL}/api`;
const ADMIN_USERNAME = process.env.TASK24E_ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.TASK24E_ADMIN_PASSWORD || "admin123456";
const VIEWER_USERNAME = process.env.TASK24E_VIEWER_USERNAME || `Task24E_viewer_${Date.now()}`;
const VIEWER_PASSWORD = process.env.TASK24E_VIEWER_PASSWORD || "Task24E_pass123";
const CDP_PORT = Number(process.env.TASK24E_CDP_PORT || 9234);
const RUN_ID = `Task24E_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const RUNTIME_DIR = path.resolve(process.cwd(), ".runtime", "task24e");
const RESULT_FILE = path.join(RUNTIME_DIR, "conversion_history_browser_result.json");

const browserCandidates = [
  process.env.TASK24E_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);

const samplePng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

const results = [];
const consoleErrors = [];
const networkFailures = [];
let browserProcess;
let cdp;
let adminToken = "";
let deviceId = "";
let mediaId = "";

function record(name, status, notes = "") {
  results.push({ name, status, notes });
  const marker = status === "passed" ? "[PASS]" : status === "blocked" ? "[BLOCKED]" : "[FAIL]";
  console.log(`${marker} ${name}${notes ? ` - ${notes}` : ""}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(fn, timeoutMs = 20000, intervalMs = 400) {
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
  const payload = { password: VIEWER_PASSWORD, display_name: "Task24E Viewer", role: "viewer", status: "active" };
  if (existing) {
    await requestJson("PUT", `/users/${existing.id}`, { token: adminToken, payload });
    return;
  }
  apiData("create viewer", await requestJson("POST", "/users", { token: adminToken, payload: { username: VIEWER_USERNAME, ...payload } }));
}

async function createDevice() {
  const payload = {
    device_code: `${RUN_ID}_DEV`,
    device_name: `${RUN_ID} Huawei SUN2000 inverter`,
    manufacturer: "huawei",
    product_series: "SUN2000",
    model: "SUN2000-50KTL",
    device_type: "pv_inverter",
    station_name: `${RUN_ID} demo station`,
    location: "Task24E browser bay",
    status: "fault",
    metadata_json: { marker: RUN_ID },
    description: `${RUN_ID} browser conversion history device.`,
  };
  const data = apiData("create device", await requestJson("POST", "/devices", { token: adminToken, payload, timeoutMs: 30000 }));
  deviceId = data.id;
}

async function uploadMedia() {
  const form = new FormData();
  form.append("file", new Blob([samplePng], { type: "image/png" }), `${RUN_ID}_pv_inverter_site.png`);
  form.append("media_type", "fault_image");
  form.append("description", `${RUN_ID} PV inverter low insulation site evidence`);
  form.append("manufacturer", "huawei");
  form.append("product_series", "SUN2000");
  form.append("device_type", "pv_inverter");
  form.append("device_id", deviceId);
  form.append("fault_type", "low_insulation_resistance");
  form.append("alarm_code", `${RUN_ID}_LOW_INSULATION`);
  const response = await fetch(`${API_BASE_URL}/media/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}`, Accept: "application/json" },
    body: form,
  });
  const body = await response.json();
  const data = apiData("upload media", { status: response.status, body });
  mediaId = data.media_id || data.id;
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
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width >= 0 && rect.height >= 0;
    };
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

async function launchBrowser() {
  const browserPath = browserCandidates.find((candidate) => candidate && fs.existsSync(candidate));
  if (!browserPath) throw new Error("No Chrome or Edge executable found");
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "em-task24e-profile-"));
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
  await waitFor(async () => Boolean(await cdp.eval("localStorage.getItem('energy_maintenance_access_token') || ''")), 15000);
}

async function createSopRunViaUi() {
  await cdp.navigate("/agents/workbench");
  await waitFor(() => cdp.eval(domScript(`
    const agent = document.querySelector("[data-testid='agent-selector']");
    const device = document.querySelector("[data-testid='device-selector']");
    const media = document.querySelector("[data-testid='media-selector']");
    const text = document.querySelector("[data-testid='agent-input']");
    if (!agent || !device || !text) return false;
    setValue(agent, "sop_planner_agent");
    setValue(device, ${JSON.stringify(deviceId)});
    if (media) setValue(media, ${JSON.stringify(mediaId)});
    setValue(text, ${JSON.stringify(`${RUN_ID} SOP conversion history browser validation.`)});
    return true;
  `)), 20000);
  await sleep(700);
  await cdp.eval(domScript(`
    const btn = document.querySelector("[data-testid='create-agent-run']");
    if (!btn || btn.disabled) return false;
    btn.click();
    return true;
  `));
  await waitFor(async () => {
    const text = await bodyText();
    return text.includes("sop_draft") && Boolean(await cdp.eval("document.querySelector('[data-testid=\"approve-sop_draft_review\"]')"));
  }, 70000);
  record("browser create SOP draft", "passed");
}

async function approveSopDraft() {
  await cdp.eval(domScript(`
    const button = document.querySelector("[data-testid='approve-sop_draft_review']");
    if (!button || button.disabled) return false;
    button.click();
    return true;
  `));
  await waitFor(async () => {
    const text = await bodyText();
    return text.includes("approved") || text.includes("已通过");
  }, 20000);
  record("browser approve SOP draft", "passed");
}

async function convertAndVerifyHistory() {
  await waitFor(async () => Boolean(await cdp.eval("document.querySelector('[data-testid=\"convert-sop_template\"]')")), 20000);
  await cdp.eval(domScript(`
    const button = document.querySelector("[data-testid='convert-sop_template']");
    if (!button || button.disabled) return false;
    button.click();
    return true;
  `));
  await waitFor(async () => {
    const historyText = await cdp.eval(`(() => {
      const el = document.querySelector('[data-testid="conversion-history-sop_template"]');
      return el ? el.innerText : '';
    })()`);
    return historyText.includes("conv-") && historyText.includes("target_id");
  }, 30000);
  const firstHistory = await cdp.eval("(() => document.querySelector('[data-testid=\"conversion-history-sop_template\"]')?.innerText || '')()");
  const convertVisibleAfterSuccess = await cdp.eval("Boolean(document.querySelector('[data-testid=\"convert-sop_template\"]'))");
  if (convertVisibleAfterSuccess) {
    throw new Error("convert button should be hidden after successful conversion status is loaded");
  }
  record("browser conversion history", "passed", firstHistory.split("\n").slice(0, 3).join(" | "));
}

async function verifyViewerReadonly() {
  await cdp.eval("localStorage.clear(); sessionStorage.clear(); true");
  await loginViaUi(VIEWER_USERNAME, VIEWER_PASSWORD);
  await cdp.navigate("/agents/workbench");
  await waitFor(async () => Boolean(await cdp.eval("document.querySelector('[data-testid=\"agent-selector\"]')")), 15000);
  const hasConvertButton = await cdp.eval("Boolean(document.querySelector('[data-testid^=\"convert-\"]'))");
  if (hasConvertButton) throw new Error("viewer should not see conversion buttons");
  const createDisabled = await cdp.eval(domScript(`
    const btn = document.querySelector("[data-testid='create-agent-run']");
    return btn ? Boolean(btn.disabled) : "missing";
  `));
  if (createDisabled !== true) throw new Error(`viewer create button should be disabled, got ${createDisabled}`);
  record("viewer conversion UI readonly", "passed");
}

async function main() {
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  apiData("health", await requestJson("GET", "/health", { timeoutMs: 8000 }));
  adminToken = await login(ADMIN_USERNAME, ADMIN_PASSWORD);
  await ensureViewer();
  await createDevice();
  await uploadMedia();
  record("preflight API/device/media", "passed", `device_id=${deviceId} media_id=${mediaId}`);
  await launchBrowser();
  await loginViaUi(ADMIN_USERNAME, ADMIN_PASSWORD);
  record("admin browser login", "passed");
  await createSopRunViaUi();
  await approveSopDraft();
  await convertAndVerifyHistory();
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
    record("Task24E browser conversion history acceptance", "failed", error.stack || error.message);
  })
  .finally(async () => {
    await shutdown();
    fs.mkdirSync(RUNTIME_DIR, { recursive: true });
    fs.writeFileSync(
      RESULT_FILE,
      JSON.stringify({
        base_url: BASE_URL,
        run_id: RUN_ID,
        device_id: deviceId,
        media_id: mediaId,
        results,
        console_errors: consoleErrors,
        network_failures: networkFailures,
        no_package_generated: true,
      }, null, 2),
      "utf8",
    );
    console.log(`RESULT_FILE=${RESULT_FILE}`);
    process.exit(results.some((item) => item.status === "failed") ? 1 : 0);
  });
