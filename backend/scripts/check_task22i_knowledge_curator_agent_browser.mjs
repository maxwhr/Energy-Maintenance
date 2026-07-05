import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE_URL = (process.env.TASK22I_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const API_BASE_URL = `${BASE_URL}/api`;
const ADMIN_USERNAME = process.env.TASK22I_ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.TASK22I_ADMIN_PASSWORD || "admin123456";
const VIEWER_USERNAME = process.env.TASK22I_VIEWER_USERNAME || `Task22I_viewer_${Date.now()}`;
const VIEWER_PASSWORD = process.env.TASK22I_VIEWER_PASSWORD || "Task22I_pass123";
const CDP_PORT = Number(process.env.TASK22I_CDP_PORT || 9229);
const RUN_ID = `Task22I_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const RUNTIME_DIR = path.resolve(process.cwd(), ".runtime", "task22i");
const RESULT_FILE = path.join(RUNTIME_DIR, "knowledge_curator_agent_browser_result.json");
const SAMPLE_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

const browserCandidates = [
  process.env.TASK22I_BROWSER_PATH,
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
let viewerToken = "";
let deviceId = "";
let mediaId = "";
let sourceRunIds = [];

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
  const payload = { password: VIEWER_PASSWORD, display_name: "Task22I Viewer", role: "viewer", status: "active" };
  if (existing) {
    await requestJson("PUT", `/users/${existing.id}`, { token: adminToken, payload });
    return;
  }
  apiData(
    "create viewer",
    await requestJson("POST", "/users", {
      token: adminToken,
      payload: { username: VIEWER_USERNAME, ...payload },
    }),
  );
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
    location: "Task22I browser bay",
    status: "fault",
    metadata_json: { marker: RUN_ID },
    description: `${RUN_ID} device for browser knowledge curator orchestration.`,
  };
  const data = apiData("create device", await requestJson("POST", "/devices", { token: adminToken, payload, timeoutMs: 30000 }));
  deviceId = data.id;
}

async function uploadMedia() {
  const form = new FormData();
  form.append("file", new Blob([SAMPLE_PNG], { type: "image/png" }), `${RUN_ID}_pv_inverter_site.png`);
  form.append("media_type", "fault_image");
  form.append("description", `${RUN_ID} browser PV inverter low insulation site evidence`);
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

async function createSourceRun(agentCode, tools) {
  const payload = {
    agent_code: agentCode,
    input_text: `${RUN_ID} SUN2000 low insulation source context for knowledge curation.`,
    device_id: deviceId,
    media_ids: [mediaId],
    tools,
    context: {
      manufacturer: "huawei",
      product_series: "SUN2000",
      device_type: "pv_inverter",
      fault_type: "low_insulation_resistance",
      alarm_code: `${RUN_ID}_LOW_INSULATION`,
      fault_description: `${RUN_ID} low insulation alarm after humid weather.`,
      source: "task22i_browser",
    },
    tool_inputs: {
      task_draft_creator: { priority: "high" },
      safety_guard: { source: agentCode },
    },
    dry_run: true,
    mock_run: false,
  };
  const run = apiData(`create ${agentCode}`, await requestJson("POST", "/agents/runs", { token: adminToken, payload, timeoutMs: 90000 }));
  return run.run_id;
}

async function contributionCount() {
  const query = new URLSearchParams({ keyword: RUN_ID, page: "1", page_size: "10" });
  const data = apiData("list contributions", await requestJson("GET", `/knowledge/contributions?${query}`, { token: adminToken }));
  return Number(data.total || 0);
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "em-task22i-profile-"));
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

async function fillKnowledgeCuratorForm() {
  await waitFor(() => cdp.eval(domScript(`
    const agent = document.querySelector("[data-testid='agent-selector']");
    const device = document.querySelector("[data-testid='device-selector']");
    const media = document.querySelector("[data-testid='media-selector']");
    const text = document.querySelector("[data-testid='agent-input']");
    if (!agent || !device || !text) return false;
    setValue(agent, "knowledge_curator_agent");
    setValue(device, ${JSON.stringify(deviceId)});
    if (media) setValue(media, ${JSON.stringify(mediaId)});
    setValue(text, ${JSON.stringify(`${RUN_ID} 请将本次 SUN2000 低绝缘阻抗告警处理过程沉淀为知识贡献草稿。`)});
    return true;
  `)), 20000);
  await sleep(600);
  await waitFor(() => cdp.eval(domScript(`
    setValue(document.querySelector("[data-testid='engineer-notes-input']"), "现场湿度高，绝缘复测后恢复，建议沉淀为待审核经验。");
    setValue(document.querySelector("[data-testid='source-runs-input']"), ${JSON.stringify(sourceRunIds.join("\\n"))});
    return true;
  `)), 10000);
}

async function createCuratorRunViaUi() {
  await fillKnowledgeCuratorForm();
  await cdp.eval(domScript(`
    const btn = document.querySelector("[data-testid='create-agent-run']");
    if (!btn || btn.disabled) return false;
    btn.click();
    return true;
  `));
  await waitFor(async () => {
    const text = await bodyText();
    return text.includes("maintenance_case_summary")
      && text.includes("knowledge_contribution_draft")
      && text.includes("kg_candidate_suggestion")
      && text.includes("evidence_trace_summary")
      && text.includes("safety_checklist");
  }, 60000);
  record("browser knowledge_curator_agent", "passed", "five artifacts displayed");
}

async function approveOneApproval() {
  await cdp.eval(domScript(`
    const buttons = Array.from(document.querySelectorAll("button")).filter(visible);
    const approve = buttons.find((item) => item.innerText.includes("通过"));
    if (!approve || approve.disabled) return false;
    approve.click();
    return true;
  `));
  await waitFor(async () => {
    const text = await bodyText();
    return text.includes("approved") || text.includes("已通过");
  }, 15000);
  record("admin approve knowledge curator approval", "passed");
}

async function verifyAdminFlow() {
  await loginViaUi(ADMIN_USERNAME, ADMIN_PASSWORD);
  record("admin browser login", "passed");
  await cdp.navigate("/agents/workbench");
  await waitFor(async () => (await bodyText()).includes("智能体工作台"), 15000);
  record("open /agents/workbench", "passed", `device_id=${deviceId}`);
  const before = await contributionCount();
  await createCuratorRunViaUi();
  await approveOneApproval();
  const after = await contributionCount();
  if (after !== before) throw new Error(`formal contribution count changed: before=${before}, after=${after}`);
  record("no formal knowledge contribution created", "passed", `count=${after}`);
}

async function verifyViewerReadonly() {
  await cdp.eval("localStorage.clear(); sessionStorage.clear(); true");
  viewerToken = await login(VIEWER_USERNAME, VIEWER_PASSWORD);
  await loginViaUi(VIEWER_USERNAME, VIEWER_PASSWORD);
  await cdp.navigate("/agents/workbench");
  await waitFor(async () => (await bodyText()).includes("智能体工作台"), 15000);
  await cdp.eval(domScript(`
    const agent = document.querySelector("[data-testid='agent-selector']");
    if (agent) setValue(agent, "knowledge_curator_agent");
    return true;
  `));
  const disabled = await cdp.eval(domScript(`
    const btn = document.querySelector("[data-testid='create-agent-run']");
    return btn ? Boolean(btn.disabled) : "missing";
  `));
  if (disabled !== true) throw new Error(`viewer create button should be disabled, got ${disabled}`);
  record("viewer cannot create curator run", "passed");
  const forbidden = await requestJson("POST", "/agents/runs", {
    token: viewerToken,
    payload: { agent_code: "knowledge_curator_agent", input_text: "viewer should be blocked", dry_run: true },
  });
  if (![401, 403].includes(forbidden.status) && [0, 200].includes(forbidden.body?.code)) {
    throw new Error("viewer API create run should be blocked");
  }
  record("viewer API create blocked", "passed");
}

async function main() {
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  apiData("health", await requestJson("GET", "/health", { timeoutMs: 8000 }));
  adminToken = await login(ADMIN_USERNAME, ADMIN_PASSWORD);
  await ensureViewer();
  await createDevice();
  await uploadMedia();
  sourceRunIds = [
    await createSourceRun("fault_diagnosis_agent", ["device_lookup", "device_history", "media_lookup", "knowledge_search", "kg_business_context", "diagnosis_rule_engine", "safety_guard"]),
    await createSourceRun("sop_planner_agent", ["device_lookup", "knowledge_search", "kg_business_context", "sop_generator", "safety_guard"]),
    await createSourceRun("task_orchestration_agent", ["device_lookup", "device_history", "record_center_lookup", "task_draft_creator", "safety_guard", "human_approval"]),
  ];
  record("preflight API/device/media/source-runs", "passed", `device_id=${deviceId} media_id=${mediaId}`);
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
    record("Task22I browser acceptance", "failed", error.stack || error.message);
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
        source_run_ids: sourceRunIds,
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
