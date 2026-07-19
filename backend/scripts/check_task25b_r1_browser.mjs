import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const BACKEND = path.resolve(import.meta.dirname, "..");
const ROOT = path.resolve(BACKEND, "..");
const RUNTIME = path.join(ROOT, ".runtime", "task25b_r1");
const BASE_URL = (process.env.TASK25B_R1_BASE_URL || "http://127.0.0.1:8013").replace(/\/$/, "");
const CREDENTIALS = process.env.TASK25B_R1_CREDENTIALS_FILE || path.join(ROOT, ".runtime", "task25a_r1", ".test_credentials.private.json");
const CDP_PORT = Number(process.env.TASK25B_R1_CDP_PORT || 9336);
fs.mkdirSync(RUNTIME, { recursive: true });

const browserPath = [
  process.env.TASK25B_R1_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean).find(fs.existsSync);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const consoleErrors = [];
const networkFailures = [];
const checks = [];
let browser;
let client;

function finish(status, extra = {}) {
  const payload = { status, base_url: BASE_URL, real_browser: true, checks, console_errors: consoleErrors,
    network_failures: networkFailures, credential_values_output: false, ...extra };
  fs.writeFileSync(path.join(RUNTIME, "browser.json"), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(payload, null, 2));
}

async function waitFor(fn, timeout = 20000) {
  const started = Date.now(); let last;
  while (Date.now() - started < timeout) {
    try { const result = await fn(); if (result) return result; } catch (error) { last = error; }
    await sleep(250);
  }
  throw last || new Error("browser wait timeout");
}

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url); this.id = 1; this.pending = new Map();
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id); if (!pending) return;
        this.pending.delete(message.id); message.error ? pending.reject(new Error(message.error.message)) : pending.resolve(message.result);
      } else if (message.method === "Runtime.exceptionThrown") consoleErrors.push(message.params?.exceptionDetails?.text || "runtime exception");
      else if (message.method === "Runtime.consoleAPICalled" && ["error", "assert"].includes(message.params?.type))
        consoleErrors.push((message.params.args || []).map((item) => item.value || item.description || "").join(" "));
      else if (message.method === "Network.loadingFailed" && !String(message.params?.errorText).includes("ERR_ABORTED"))
        networkFailures.push({ error: message.params?.errorText, type: message.params?.type });
    };
  }
  ready() { return new Promise((resolve, reject) => { this.ws.onopen = resolve; this.ws.onerror = reject; }); }
  send(method, params = {}) { const id = this.id++; return new Promise((resolve, reject) => {
    this.pending.set(id, { resolve, reject }); this.ws.send(JSON.stringify({ id, method, params }));
  }); }
  async eval(expression) { const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "browser evaluation failed"); return result.result?.value; }
  async navigate(url) { await this.send("Page.navigate", { url }); await waitFor(() => this.eval("document.readyState === 'complete'")); await sleep(900); }
}

async function login(credentials) {
  const response = await fetch(`${BASE_URL}/api/auth/login`, { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(credentials) });
  const body = await response.json();
  if (!response.ok || !body?.data?.access_token) throw new Error(`login failed ${response.status}`);
  const user = body.data.user;
  return { token: body.data.access_token, user: { id: user.id, username: user.username,
    displayName: user.display_name || user.username, role: user.role, roles: [user.role], status: user.status } };
}

async function setAuth(auth) {
  await client.eval(`localStorage.setItem('energy_maintenance_access_token', ${JSON.stringify(auth.token)});
    localStorage.setItem('user_info', ${JSON.stringify(JSON.stringify(auth.user))}); true`);
}

async function pageCheck(route, expected, forbidden = []) {
  await client.navigate(`${BASE_URL}${route}`);
  const body = await waitFor(async () => { const text = await client.eval("document.body?.innerText || ''"); return text.includes(expected) ? text : null; });
  const forbiddenFound = forbidden.filter((item) => body.includes(item));
  if (forbiddenFound.length) throw new Error(`forbidden page text: ${forbiddenFound.join(',')}`);
  if (/DASHSCOPE_API_KEY|DASHVECTOR_API_KEY|Authorization:\s*Bearer/i.test(body)) throw new Error("secret marker rendered");
  checks.push({ type: "page", route, expected_found: true, forbidden_found: [] });
}

async function api(pathname, token, options = {}) {
  const response = await fetch(`${BASE_URL}${pathname}`, { ...options, headers: { "content-type": "application/json",
    authorization: `Bearer ${token}`, ...(options.headers || {}) } });
  let body = {}; try { body = await response.json(); } catch {}
  return { status: response.status, body };
}

async function main() {
  if (!browserPath) throw new Error("Chrome or Edge not found");
  if (!fs.existsSync(CREDENTIALS)) throw new Error("secure credential file missing");
  const values = JSON.parse(fs.readFileSync(CREDENTIALS, "utf8"));
  const admin = await login(values.admin);
  const viewer = await login(values.viewer);
  const strategy = await api("/api/retrieval/strategy-status", admin.token);
  if (strategy.status !== 200 || strategy.body?.data?.version !== "task25b-r1" || strategy.body?.data?.quality_gate_status !== "PASSED")
    throw new Error("R1 strategy status is not current or passed");
  checks.push({ type: "api", name: "admin_strategy_view", passed: true, default_strategy: strategy.body.data.default_strategy });
  const viewerEval = await api("/api/retrieval/evaluate", viewer.token, { method: "POST", body: JSON.stringify({ dataset_split: "dev" }) });
  const viewerIndex = await api("/api/vector-search/reindex-approved", viewer.token, { method: "POST", body: JSON.stringify({ dry_run: true, test_only: true, limit: 1 }) });
  if (viewerEval.status !== 403 || viewerIndex.status !== 403) throw new Error("viewer RBAC boundary failed");
  checks.push({ type: "api", name: "viewer_evaluate_forbidden", passed: true });
  checks.push({ type: "api", name: "viewer_index_forbidden", passed: true });

  const profile = path.join(RUNTIME, "browser-profile");
  browser = spawn(browserPath, ["--headless=new", `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--disable-extensions", "about:blank"], { windowsHide: true });
  const page = await waitFor(async () => { const response = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`);
    const pages = await response.json(); return pages.find((item) => item.type === "page" && item.webSocketDebuggerUrl); });
  client = new CDP(page.webSocketDebuggerUrl); await client.ready();
  await Promise.all([client.send("Page.enable"), client.send("Runtime.enable"), client.send("Network.enable")]);
  await client.navigate(BASE_URL);
  await setAuth(viewer);
  await pageCheck("/system/retrieval-quality", "无权访问此页面", ["执行 test split 评测"]);
  await setAuth(admin);
  await pageCheck("/system/retrieval-quality", "PASSED", ["执行 test split 评测"]);
  await pageCheck("/knowledge/search", "自适应检索（推荐）");
  await pageCheck("/multimodal", "跨模态检索");
  const failed = consoleErrors.length > 0 || networkFailures.length > 0;
  finish(failed ? "FAILED" : "PASSED", { page_errors: consoleErrors.length });
  return failed ? 1 : 0;
}

main().then((code) => { client?.ws?.close(); browser?.kill(); process.exitCode = code; }).catch((error) => {
  finish("FAILED", { error: `${error.name}: ${error.message}`, page_errors: consoleErrors.length });
  client?.ws?.close(); browser?.kill(); process.exitCode = 1;
});
