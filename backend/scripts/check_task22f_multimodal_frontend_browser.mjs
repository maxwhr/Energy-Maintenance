import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE_URL = (process.env.TASK22F_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const API_BASE_URL = `${BASE_URL}/api`;
const ADMIN_USERNAME = process.env.TASK22F_ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.TASK22F_ADMIN_PASSWORD || "admin123456";
const EXPERT_USERNAME = process.env.TASK22F_EXPERT_USERNAME || "expert";
const EXPERT_PASSWORD = process.env.TASK22F_EXPERT_PASSWORD || "admin123456";
const ENGINEER_USERNAME = process.env.TASK22F_ENGINEER_USERNAME || "engineer";
const ENGINEER_PASSWORD = process.env.TASK22F_ENGINEER_PASSWORD || "admin123456";
const VIEWER_USERNAME = process.env.TASK22F_VIEWER_USERNAME || "viewer";
const VIEWER_PASSWORD = process.env.TASK22F_VIEWER_PASSWORD || "admin123456";
const CDP_PORT = Number(process.env.TASK22F_CDP_PORT || 9226);
const RUN_ID = `Task22F_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const RUNTIME_DIR = path.resolve(process.cwd(), "..", ".runtime", "task22f");
const RESULT_FILE = path.join(RUNTIME_DIR, "multimodal_frontend_browser_result.json");
const SAMPLE_FILE = path.join(RUNTIME_DIR, `${RUN_ID}_pv_inverter_alarm.png`);

const SAMPLE_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

const browserCandidates = [
  process.env.TASK22F_BROWSER_PATH,
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
let mediaId = "";

function record(name, status, notes = "") {
  results.push({ name, status, notes });
  const marker = status === "passed" ? "[PASS]" : status === "blocked" ? "[BLOCKED]" : "[FAIL]";
  console.log(`${marker} ${name}${notes ? ` - ${notes}` : ""}`);
}

function step(name) {
  console.log(`[STEP] ${name}`);
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

function findBrowserPath() {
  for (const candidate of browserCandidates) {
    if (candidate && fs.existsSync(candidate)) return candidate;
  }
  return null;
}

async function requestJson(method, pathOrUrl, { token = "", payload = undefined, timeoutMs = 15000 } = {}) {
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
    const raw = await response.text();
    let parsed = {};
    try {
      parsed = raw ? JSON.parse(raw) : {};
    } catch {
      parsed = { code: response.status, message: raw.slice(0, 300), data: null };
    }
    return { status: response.status, body: parsed };
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

async function apiLogin(username, password) {
  const response = await requestJson("POST", "/auth/login", { payload: { username, password } });
  const data = apiData(`login ${username}`, response);
  if (!data?.access_token) throw new Error(`login ${username} did not return access_token`);
  return { token: data.access_token, user: data.user };
}

async function ensureUser(username, role, displayName, password = VIEWER_PASSWORD) {
  const query = new URLSearchParams({ keyword: username, page: "1", page_size: "100" });
  const listed = apiData(`list user ${username}`, await requestJson("GET", `/users?${query}`, { token: adminToken }));
  const existing = (listed.items || []).find((item) => item.username === username);
  const payload = {
    username,
    password,
    display_name: displayName,
    role,
    status: "active",
  };
  if (existing) {
    return apiData(
      `update user ${username}`,
      await requestJson("PUT", `/users/${existing.id}`, {
        token: adminToken,
        payload: { password, display_name: displayName, role, status: "active" },
      }),
    );
  }
  const created = await requestJson("POST", "/users", { token: adminToken, payload });
  if (created.body?.message === "Username already exists") {
    const retry = apiData(`retry list user ${username}`, await requestJson("GET", `/users?${query}`, { token: adminToken }));
    const match = (retry.items || []).find((item) => item.username === username);
    if (match) {
      return apiData(
        `update existing user ${username}`,
        await requestJson("PUT", `/users/${match.id}`, {
          token: adminToken,
          payload: { password, display_name: displayName, role, status: "active" },
        }),
      );
    }
  }
  return apiData(`create user ${username}`, created);
}

async function findUploadedMedia() {
  const query = new URLSearchParams({ keyword: RUN_ID, page: "1", page_size: "10" });
  const page = apiData("find uploaded media", await requestJson("GET", `/media?${query}`, { token: adminToken }));
  const item = (page.items || []).find((entry) =>
    [entry.file_name, entry.original_file_name, entry.description].some((value) => String(value || "").includes(RUN_ID)),
  );
  if (!item?.id) throw new Error(`uploaded media not found for ${RUN_ID}`);
  return item.id;
}

async function listMediaJobs() {
  return apiData("list media jobs", await requestJson("GET", `/multimodal/media/${mediaId}/jobs?page=1&page_size=20`, { token: adminToken }));
}

async function listOcrResults() {
  return apiData("list OCR results", await requestJson("GET", `/multimodal/media/${mediaId}/ocr-results?page=1&page_size=20`, { token: adminToken }));
}

async function listAnalyses() {
  return apiData("list analyses", await requestJson("GET", `/multimodal/media/${mediaId}/analyses?page=1&page_size=20`, { token: adminToken }));
}

async function listEvidenceLinks() {
  const query = new URLSearchParams({ media_id: mediaId, page: "1", page_size: "20" });
  return apiData("list evidence links", await requestJson("GET", `/multimodal/evidence-links?${query}`, { token: adminToken }));
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
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
      if (msg.error) entry.reject(new Error(`${msg.error.message || "CDP error"} ${JSON.stringify(msg.error.data || "")}`));
      else entry.resolve(msg.result);
      return;
    }
    if (msg.method === "Runtime.consoleAPICalled" && ["error", "assert"].includes(msg.params?.type)) {
      consoleErrors.push({
        type: msg.params.type,
        text: (msg.params.args || []).map((arg) => arg.value || arg.description || "").join(" "),
      });
    }
    if (msg.method === "Runtime.exceptionThrown") {
      consoleErrors.push({
        type: "exception",
        text: msg.params?.exceptionDetails?.text || msg.params?.exceptionDetails?.exception?.description || "Runtime exception",
      });
    }
    if (msg.method === "Network.loadingFailed" && msg.params?.errorText && !String(msg.params.errorText).includes("net::ERR_ABORTED")) {
      networkFailures.push({
        errorText: msg.params.errorText,
        type: msg.params.type,
      });
    }
    const listeners = this.events.get(msg.method) || [];
    for (const listener of listeners.splice(0)) listener(msg.params);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
    });
  }

  async eval(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Evaluation failed");
    }
    return result.result?.value;
  }

  async navigate(pagePath) {
    const url = pagePath.startsWith("http") ? pagePath : `${BASE_URL}${pagePath}`;
    await this.send("Page.navigate", { url });
    await sleep(800);
    await waitFor(async () => ["complete", "interactive"].includes(await this.eval("document.readyState")), 15000);
    await sleep(900);
  }

  close() {
    try {
      this.ws.close();
    } catch {
      // best effort
    }
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
    const findByText = (selector, texts, enabledOnly = true) => {
      const list = Array.from(document.querySelectorAll(selector)).filter(visible);
      return list.find((el) => (!enabledOnly || !el.disabled) && texts.some((text) => labelText(el).includes(text)));
    };
    ${body}
  })()`;
}

async function clickByText(texts, { enabledOnly = true, timeoutMs = 10000 } = {}) {
  const textList = Array.isArray(texts) ? texts : [texts];
  const res = await waitFor(
    () =>
      cdp.eval(domScript(`
        const el = findByText("button,a,[role='button'],summary,input[type='submit']", ${JSON.stringify(textList)}, ${JSON.stringify(enabledOnly)});
        if (!el) return null;
        el.scrollIntoView({ block: "center", inline: "center" });
        el.click();
        return { ok: true, text: labelText(el), disabled: Boolean(el.disabled) };
      `)),
    timeoutMs,
  );
  await sleep(900);
  return res;
}

async function clickFirstSubmit() {
  const res = await cdp.eval(domScript(`
    const el = Array.from(document.querySelectorAll("form button[type='submit'], form input[type='submit']")).filter(visible)[0];
    if (!el || el.disabled) return { ok: false };
    el.scrollIntoView({ block: "center", inline: "center" });
    el.click();
    return { ok: true, text: labelText(el) };
  `));
  await sleep(900);
  return res;
}

async function fillBySelector(selector, value, index = 0) {
  return cdp.eval(domScript(`
    const inputs = Array.from(document.querySelectorAll(${JSON.stringify(selector)})).filter(visible);
    return setValue(inputs[${index}], ${JSON.stringify(value)});
  `));
}

async function fillByLabel(label, value) {
  return cdp.eval(domScript(`
    const labels = Array.from(document.querySelectorAll("label")).filter(visible);
    const holder = labels.find((item) => labelText(item).includes(${JSON.stringify(label)}));
    const field = holder?.querySelector("input:not([type='file']),textarea,select");
    return setValue(field, ${JSON.stringify(value)});
  `));
}

async function fillByPlaceholder(placeholderPart, value) {
  return cdp.eval(domScript(`
    const fields = Array.from(document.querySelectorAll("input,textarea")).filter(visible);
    const field = fields.find((item) => String(item.placeholder || "").includes(${JSON.stringify(placeholderPart)}));
    return setValue(field, ${JSON.stringify(value)});
  `));
}

async function setFileInput(filePath) {
  const document = await cdp.send("DOM.getDocument", { depth: -1, pierce: true });
  const node = await cdp.send("DOM.querySelector", {
    nodeId: document.root.nodeId,
    selector: "input[type=file]",
  });
  if (!node.nodeId) return false;
  await cdp.send("DOM.setFileInputFiles", { nodeId: node.nodeId, files: [filePath] });
  await sleep(500);
  return true;
}

async function bodyText() {
  return cdp.eval("document.body ? document.body.innerText : ''");
}

async function currentPath() {
  return cdp.eval("location.pathname + location.search");
}

async function textIncludes(texts) {
  const text = await bodyText();
  return (Array.isArray(texts) ? texts : [texts]).some((item) => text.includes(item));
}

async function waitForAnyText(texts, timeoutMs = 15000) {
  return waitFor(() => textIncludes(texts), timeoutMs);
}

async function loginViaUi(username, password, label) {
  step(`browser login ${username}`);
  await cdp.navigate("/login");
  await fillBySelector("input[autocomplete='username'], input:not([type='password'])", username);
  await fillBySelector("input[type='password']", password);
  const clicked = await clickFirstSubmit();
  if (!clicked.ok) throw new Error("login submit button not found");
  try {
    await waitFor(async () => {
      const pathName = await currentPath();
      const text = await bodyText();
      const token = await cdp.eval("localStorage.getItem('energy_maintenance_access_token') || ''");
      return !pathName.startsWith("/login") && Boolean(token) && (text.includes(label) || text.includes("运行总览") || text.includes("工作台"));
    }, 15000);
  } catch (error) {
    const pathName = await currentPath();
    const text = await bodyText();
    const token = await cdp.eval("localStorage.getItem('energy_maintenance_access_token') || ''");
    throw new Error(`browser login ${username} failed; path=${pathName}; token=${Boolean(token)}; text=${text.slice(0, 500)}`);
  }
}

async function logoutLocal() {
  await cdp.navigate("/login");
  await cdp.eval("localStorage.clear(); sessionStorage.clear(); true");
  await sleep(400);
}

async function uploadMediaViaBrowser() {
  step("browser media upload");
  await cdp.navigate("/media");
  await waitForAnyText(["媒体资料", "上传"]);
  if (!(await setFileInput(SAMPLE_FILE))) throw new Error("media file input not found");
  await fillByLabel("人工描述", `${RUN_ID} 华为 SUN2000 告警屏幕浏览器验收图片`);
  await fillByLabel("告警代码", `${RUN_ID}_ALARM`);
  await clickByText(["上传媒体", "上传"], { enabledOnly: true });
  await waitFor(async () => {
    try {
      mediaId = await findUploadedMedia();
      return mediaId;
    } catch {
      return "";
    }
  }, 25000);
  record("browser media upload", "passed", `media_id=${mediaId}`);
}

async function verifyMultimodalPageAdmin() {
  step("admin multimodal page");
  await cdp.navigate(`/multimodal?media_id=${encodeURIComponent(mediaId)}`);
  await waitForAnyText(["多模态证据中心", "Provider", "处理任务"]);
  record("open /multimodal", "passed", "page rendered with selected media context");

  await clickByText(["检查"], { enabledOnly: true });
  await waitForAnyText(["最近调用结果", "trace_id", "blocked", "not_configured"], 15000);
  record("provider check button", "passed", "admin can trigger provider config check without external call");

  await clickByText(["dry-run"], { enabledOnly: true });
  await waitForAnyText(["最近调用结果", "external_api_called=false", "trace_id"], 15000);
  record("provider dry-run button", "passed", "dry-run result is displayed");

  const initialJobs = (await listMediaJobs()).items?.length || 0;
  await clickByText(["OCR dry-run"], { enabledOnly: true });
  await waitFor(async () => ((await listMediaJobs()).items?.length || 0) > initialJobs, 20000);
  record("OCR dry-run button", "passed", "job persisted after browser click");

  const jobsAfterOcr = (await listMediaJobs()).items?.length || 0;
  await clickByText(["AI dry-run"], { enabledOnly: true });
  await waitFor(async () => ((await listMediaJobs()).items?.length || 0) > jobsAfterOcr, 20000);
  record("AI dry-run button", "passed", "job persisted after browser click");

  const analysesBefore = (await listAnalyses()).items?.length || 0;
  await clickByText(["AI mock-run"], { enabledOnly: true });
  await waitFor(async () => ((await listAnalyses()).items?.length || 0) > analysesBefore, 20000);
  await waitForAnyText(["AI 多模态分析", "模拟", "mocked"], 15000);
  record("AI mock-run button", "passed", "analysis result persisted and displayed");

  const ocrBefore = (await listOcrResults()).items?.length || 0;
  await clickByText(["OCR mock-run"], { enabledOnly: true });
  await waitFor(async () => ((await listOcrResults()).items?.length || 0) > ocrBefore, 20000);
  await waitForAnyText(["OCR 结果", "模拟", "mocked"], 15000);
  record("OCR mock-run button", "passed", "OCR result persisted and displayed");

  await clickByText(["确认"], { enabledOnly: true });
  await waitFor(async () => {
    const analyses = (await listAnalyses()).items || [];
    return analyses.some((item) => item.human_review_status === "accepted");
  }, 15000);
  record("analysis review button", "passed", "admin accepted AI analysis");

  const linksBefore = (await listEvidenceLinks()).items?.length || 0;
  await fillByPlaceholder("来源 ID", `${RUN_ID}_trace`);
  await clickByText(["创建链接"], { enabledOnly: true });
  await waitFor(async () => ((await listEvidenceLinks()).items?.length || 0) > linksBefore, 15000);
  record("evidence link form", "passed", "evidence link persisted");

  await fillByLabel("任务描述", `${RUN_ID} 创建 dry-run Agent Run，验证 steps tool calls artifacts approvals events`);
  await clickByText(["创建 dry-run Agent Run"], { enabledOnly: true });
  await waitForAnyText(["Agent", "工具调用", "Artifacts", "审批"], 25000);
  const runs = apiData(
    "list agent runs",
    await requestJson("GET", `/agents/runs?${new URLSearchParams({ keyword: RUN_ID, page: "1", page_size: "5" })}`, { token: adminToken }),
  );
  if (!runs.items?.length) throw new Error("created agent run not found by keyword");
  record("agent dry-run entry", "passed", `run_id=${runs.items[0].run_id || runs.items[0].id}`);
}

async function verifyViewerReadonly() {
  step("viewer readonly multimodal page");
  await logoutLocal();
  await loginViaUi(VIEWER_USERNAME, VIEWER_PASSWORD, "只读用户");
  await cdp.navigate(`/multimodal?media_id=${encodeURIComponent(mediaId)}`);
  await waitForAnyText(["多模态证据中心", "处理任务"], 15000);
  const disabledState = await cdp.eval(domScript(`
    const labels = ["OCR dry-run", "AI dry-run", "AI mock-run", "OCR mock-run", "创建 dry-run Agent Run", "创建链接"];
    const buttons = Array.from(document.querySelectorAll("button")).filter(visible);
    const state = {};
    for (const label of labels) {
      const btn = buttons.find((item) => labelText(item).includes(label));
      state[label] = btn ? Boolean(btn.disabled) : "missing";
    }
    return state;
  `));
  if (!disabledState["OCR dry-run"] || !disabledState["AI dry-run"] || !disabledState["创建 dry-run Agent Run"]) {
    throw new Error(`viewer write controls are not disabled: ${JSON.stringify(disabledState)}`);
  }
  const noEvidenceForm = !(await textIncludes("创建链接"));
  record("viewer readonly UI", "passed", `disabled=${JSON.stringify(disabledState)}, evidenceFormHidden=${noEvidenceForm}`);
}

async function verifyEngineerExpertUi() {
  step("engineer multimodal permissions");
  await logoutLocal();
  await loginViaUi(ENGINEER_USERNAME, ENGINEER_PASSWORD, "工程师");
  await cdp.navigate(`/multimodal?media_id=${encodeURIComponent(mediaId)}`);
  await waitForAnyText(["多模态证据中心", "处理任务"], 15000);
  const engineerState = await cdp.eval(domScript(`
    const labels = ["OCR dry-run", "AI dry-run", "AI mock-run", "OCR mock-run", "创建 dry-run Agent Run"];
    const buttons = Array.from(document.querySelectorAll("button")).filter(visible);
    const state = {};
    for (const label of labels) {
      const btn = buttons.find((item) => labelText(item).includes(label));
      state[label] = btn ? Boolean(btn.disabled) : "missing";
    }
    return state;
  `));
  if (engineerState["OCR dry-run"] || engineerState["AI dry-run"] || engineerState["创建 dry-run Agent Run"]) {
    throw new Error(`engineer dry-run controls should be enabled: ${JSON.stringify(engineerState)}`);
  }
  if (!engineerState["AI mock-run"] || !engineerState["OCR mock-run"]) {
    throw new Error(`engineer mock-run controls should be disabled: ${JSON.stringify(engineerState)}`);
  }
  record("engineer browser permissions", "passed", JSON.stringify(engineerState));

  step("expert multimodal permissions");
  await logoutLocal();
  await loginViaUi(EXPERT_USERNAME, EXPERT_PASSWORD, "专家");
  await cdp.navigate(`/multimodal?media_id=${encodeURIComponent(mediaId)}`);
  await waitForAnyText(["多模态证据中心", "AI 多模态分析"], 15000);
  const expertState = await cdp.eval(domScript(`
    const labels = ["AI mock-run", "OCR mock-run", "创建 dry-run Agent Run", "确认"];
    const buttons = Array.from(document.querySelectorAll("button")).filter(visible);
    const state = {};
    for (const label of labels) {
      const btn = buttons.find((item) => labelText(item).includes(label));
      state[label] = btn ? Boolean(btn.disabled) : "missing";
    }
    return state;
  `));
  if (expertState["AI mock-run"] || expertState["OCR mock-run"] || expertState["创建 dry-run Agent Run"]) {
    throw new Error(`expert mock/run controls should be enabled: ${JSON.stringify(expertState)}`);
  }
  record("expert browser permissions", "passed", JSON.stringify(expertState));
}

async function launchBrowser() {
  const browserPath = findBrowserPath();
  if (!browserPath) throw new Error("No Chrome or Edge executable found");
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "em-task22f-profile-"));
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

async function main() {
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  fs.writeFileSync(SAMPLE_FILE, SAMPLE_PNG);

  step("preflight API");
  apiData("health", await requestJson("GET", "/health", { timeoutMs: 8000 }));
  const admin = await apiLogin(ADMIN_USERNAME, ADMIN_PASSWORD);
  adminToken = admin.token;
  await ensureUser(EXPERT_USERNAME, "expert", "Task22F Expert", EXPERT_PASSWORD);
  await ensureUser(ENGINEER_USERNAME, "engineer", "Task22F Engineer", ENGINEER_PASSWORD);
  await ensureUser(VIEWER_USERNAME, "viewer", "Task22F Viewer", VIEWER_PASSWORD);
  await apiLogin(EXPERT_USERNAME, EXPERT_PASSWORD);
  await apiLogin(ENGINEER_USERNAME, ENGINEER_PASSWORD);
  viewerToken = (await apiLogin(VIEWER_USERNAME, VIEWER_PASSWORD)).token;
  record(
    "preflight API and users",
    "passed",
    `admin=${ADMIN_USERNAME}, expert=${EXPERT_USERNAME}, engineer=${ENGINEER_USERNAME}, viewer=${VIEWER_USERNAME}, viewerToken=${Boolean(viewerToken)}`,
  );

  await launchBrowser();
  step("browser admin login");
  await logoutLocal();
  await loginViaUi(ADMIN_USERNAME, ADMIN_PASSWORD, "管理员");
  record("admin browser login", "passed");

  await uploadMediaViaBrowser();
  await verifyMultimodalPageAdmin();
  await verifyEngineerExpertUi();
  await verifyViewerReadonly();

  const blockingConsoleErrors = consoleErrors.filter((item) => !String(item.text || "").includes("ResizeObserver loop"));
  if (blockingConsoleErrors.length) {
    record("browser console errors", "failed", JSON.stringify(blockingConsoleErrors.slice(0, 5)));
  } else {
    record("browser console errors", "passed", "no blocking runtime errors");
  }
  if (networkFailures.length) {
    record("browser network failures", "failed", JSON.stringify(networkFailures.slice(0, 5)));
  } else {
    record("browser network failures", "passed", "no unexpected network failures");
  }
}

async function shutdown() {
  if (cdp) cdp.close();
  if (browserProcess) {
    try {
      browserProcess.kill();
    } catch {
      // best effort
    }
  }
}

main()
  .catch((error) => {
    record("Task22F browser acceptance", "failed", error.stack || error.message);
  })
  .finally(async () => {
    await shutdown();
    fs.mkdirSync(RUNTIME_DIR, { recursive: true });
    fs.writeFileSync(
      RESULT_FILE,
      JSON.stringify(
        {
          base_url: BASE_URL,
          run_id: RUN_ID,
          media_id: mediaId,
          result_file: RESULT_FILE,
          sample_file: SAMPLE_FILE,
          results,
          console_errors: consoleErrors,
          network_failures: networkFailures,
          no_package_generated: true,
        },
        null,
        2,
      ),
      "utf8",
    );
    console.log(`RESULT_FILE=${RESULT_FILE}`);
    const failed = results.filter((item) => item.status === "failed");
    process.exit(failed.length ? 1 : 0);
  });
