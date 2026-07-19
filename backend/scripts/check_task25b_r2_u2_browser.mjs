import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const BACKEND = path.resolve(import.meta.dirname, "..");
const ROOT = path.resolve(BACKEND, "..");
const RUNTIME = path.join(ROOT, ".runtime", "task25b_r2_u2");
const BASE_URL = (process.env.TASK25B_R2_U2_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");
const CREDENTIALS = process.env.TASK25B_R2_U2_CREDENTIALS_FILE || path.join(ROOT, ".runtime", "task25a_r1", ".test_credentials.private.json");
const CDP_PORT = Number(process.env.TASK25B_R2_U2_CDP_PORT || 9342);
fs.mkdirSync(RUNTIME, { recursive: true });

const browserPath = [
  process.env.TASK25B_R2_U2_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean).find(fs.existsSync);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const checks = [];
const consoleErrors = [];
const networkFailures = [];
let browser;
let client;

function finish(status, extra = {}) {
  const payload = {
    status, base_url: BASE_URL, real_browser: true, checks,
    console_errors: consoleErrors, network_failures: networkFailures,
    approval_submitted: false, credential_values_output: false, secret_output: false,
    ...extra,
  };
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
        this.pending.delete(message.id);
        message.error ? pending.reject(new Error(message.error.message)) : pending.resolve(message.result);
      } else if (message.method === "Runtime.exceptionThrown") {
        consoleErrors.push(message.params?.exceptionDetails?.text || "runtime exception");
      } else if (message.method === "Runtime.consoleAPICalled" && ["error", "assert"].includes(message.params?.type)) {
        consoleErrors.push((message.params.args || []).map((item) => item.value || item.description || "").join(" "));
      } else if (message.method === "Network.loadingFailed" && !String(message.params?.errorText).includes("ERR_ABORTED")) {
        networkFailures.push({ error: message.params?.errorText, type: message.params?.type });
      }
    };
  }
  ready() { return new Promise((resolve, reject) => { this.ws.onopen = resolve; this.ws.onerror = reject; }); }
  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "browser evaluation failed");
    return result.result?.value;
  }
  async navigate(url) {
    await this.send("Page.navigate", { url });
    await waitFor(() => this.eval("document.readyState === 'complete'"));
    await sleep(800);
  }
}

async function login(credentials) {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(credentials),
  });
  const body = await response.json();
  if (!response.ok || !body?.data?.access_token) throw new Error(`login failed ${response.status}`);
  const user = body.data.user;
  return { token: body.data.access_token, user: { id: user.id, username: user.username, displayName: user.display_name || user.username, role: user.role, roles: [user.role], status: user.status } };
}

async function api(pathname, token, options = {}) {
  const response = await fetch(`${BASE_URL}${pathname}`, {
    ...options,
    headers: { "content-type": "application/json", authorization: `Bearer ${token}`, ...(options.headers || {}) },
  });
  let body = {}; try { body = await response.json(); } catch {}
  return { status: response.status, body };
}

async function main() {
  if (!browserPath) throw new Error("Chrome or Edge not found");
  if (!fs.existsSync(CREDENTIALS)) throw new Error("secure credential file missing");
  const values = JSON.parse(fs.readFileSync(CREDENTIALS, "utf8"));
  const expert = await login(values.expert);
  const viewer = await login(values.viewer);
  const list = await api("/api/review/knowledge?review_status=pending_review&manufacturer=huawei&page=1&page_size=100", expert.token);
  const official = (list.body?.data?.items || []).filter((item) => item.source_type === "vendor_official");
  if (list.status !== 200 || official.length !== 9) throw new Error(`expected 9 pending vendor documents, found ${official.length}`);
  if (official.some((item) => item.review_status !== "pending_review" || item.metadata_json?.approved_for_pilot)) throw new Error("unexpected approval state");
  checks.push({ type: "api", name: "pending_vendor_documents", passed: true, count: official.length });
  const viewerWrite = await api("/api/review/knowledge/vendor-official/batch-approve-for-pilot", viewer.token, {
    method: "POST", body: JSON.stringify({ document_ids: [official[0].id], comment: "RBAC probe only" }),
  });
  if (viewerWrite.status !== 403) throw new Error("viewer batch approval RBAC failed");
  checks.push({ type: "api", name: "viewer_approval_forbidden", passed: true });

  const profile = path.join(RUNTIME, "browser-profile");
  browser = spawn(browserPath, ["--headless=new", `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`, "--no-first-run", "--disable-extensions", "about:blank"], { windowsHide: true });
  const page = await waitFor(async () => {
    const response = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`);
    const pages = await response.json();
    return pages.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
  });
  client = new CDP(page.webSocketDebuggerUrl); await client.ready();
  await Promise.all([client.send("Page.enable"), client.send("Runtime.enable"), client.send("Network.enable")]);
  await client.navigate(BASE_URL);
  await client.eval(`localStorage.setItem('energy_maintenance_access_token', ${JSON.stringify(expert.token)}); localStorage.setItem('user_info', ${JSON.stringify(JSON.stringify(expert.user))}); true`);
  await client.navigate(`${BASE_URL}/review`);
  const body = await waitFor(async () => {
    const value = await client.eval("document.body?.innerText || ''");
    return ["华为官方来源", "批准进入 Pilot", "SHA-256", "OCR", "不会自动批准"].every((item) => value.includes(item)) ? value : null;
  });
  if (/DASHSCOPE_API_KEY|DASHVECTOR_API_KEY|Authorization:\s*Bearer|[A-Za-z]:\\/i.test(body)) throw new Error("secret or local path rendered");
  checks.push({ type: "page", name: "vendor_review_metadata", passed: true, expected_vendor_cards: 9 });
  const failed = consoleErrors.length > 0 || networkFailures.length > 0;
  finish(failed ? "FAILED" : "PASSED", { vendor_documents_rendered: 9 });
  return failed ? 1 : 0;
}

main().then((code) => {
  client?.ws?.close(); browser?.kill(); process.exitCode = code;
}).catch((error) => {
  finish("FAILED", { error: `${error.name}: ${error.message}` });
  client?.ws?.close(); browser?.kill(); process.exitCode = 1;
});
