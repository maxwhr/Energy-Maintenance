import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const BACKEND = path.resolve(import.meta.dirname, "..");
const ROOT = path.resolve(BACKEND, "..");
const RUNTIME = path.join(ROOT, ".runtime", "task25b");
const BASE_URL = (process.env.TASK25B_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const CREDENTIALS = process.env.TASK25B_CREDENTIALS_FILE || path.join(ROOT, ".runtime", "task25a_r1", ".test_credentials.private.json");
const CDP_PORT = Number(process.env.TASK25B_CDP_PORT || 9335);
fs.mkdirSync(RUNTIME, { recursive: true });

const browserCandidates = [
  process.env.TASK25B_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);
const browserPath = browserCandidates.find((item) => fs.existsSync(item));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const consoleErrors = [];
const networkFailures = [];
let browser;
let client;

function writeResult(status, extra = {}) {
  const payload = { status, base_url: BASE_URL, real_browser: true, console_errors: consoleErrors, network_failures: networkFailures, results, ...extra };
  fs.writeFileSync(path.join(RUNTIME, "browser.json"), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(payload, null, 2));
}

async function waitFor(fn, timeout = 20000) {
  const started = Date.now();
  let last;
  while (Date.now() - started < timeout) {
    try { const value = await fn(); if (value) return value; } catch (error) { last = error; }
    await sleep(250);
  }
  throw last || new Error("browser wait timeout");
}

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 1;
    this.pending = new Map();
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
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
    const value = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (value.exceptionDetails) throw new Error(value.exceptionDetails.text || "browser evaluation failed");
    return value.result?.value;
  }
  async navigate(url) {
    await this.send("Page.navigate", { url });
    await waitFor(() => this.eval("document.readyState === 'complete'"));
    await sleep(1200);
  }
}

async function login() {
  if (!fs.existsSync(CREDENTIALS)) throw new Error("secure browser credential file is missing");
  const credentials = JSON.parse(fs.readFileSync(CREDENTIALS, "utf8")).admin;
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ username: credentials.username, password: credentials.password }),
  });
  const body = await response.json();
  if (!response.ok || !body?.data?.access_token) throw new Error(`browser login failed: HTTP ${response.status}`);
  const user = body.data.user;
  return {
    token: body.data.access_token,
    user: { id: user.id, username: user.username, displayName: user.display_name || user.username, role: user.role, roles: [user.role], status: user.status },
  };
}

async function pageCheck(route, expectedText, screenshotName) {
  await client.navigate(`${BASE_URL}${route}`);
  const text = await waitFor(async () => {
    const body = await client.eval("document.body?.innerText || ''");
    return body.includes(expectedText) ? body : null;
  });
  const screenshot = await client.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  fs.writeFileSync(path.join(RUNTIME, screenshotName), Buffer.from(screenshot.data, "base64"));
  results.push({ route, expected_text_found: true, body_length: text.length, screenshot: screenshotName });
}

async function main() {
  if (!browserPath) throw new Error("Chrome or Edge browser executable not found");
  const auth = await login();
  const profile = path.join(RUNTIME, "browser-profile");
  browser = spawn(browserPath, ["--headless=new", `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`, "--no-first-run", "--disable-extensions", "about:blank"], { windowsHide: true });
  const page = await waitFor(async () => {
    const response = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`);
    const pages = await response.json();
    return pages.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
  });
  client = new CDP(page.webSocketDebuggerUrl);
  await client.ready();
  await Promise.all([client.send("Page.enable"), client.send("Runtime.enable"), client.send("Network.enable")]);
  await client.navigate(BASE_URL);
  await client.eval(`localStorage.setItem('energy_maintenance_access_token', ${JSON.stringify(auth.token)}); localStorage.setItem('user_info', ${JSON.stringify(JSON.stringify(auth.user))}); true`);
  await pageCheck("/system/retrieval-quality", "检索质量与向量索引", "retrieval-quality.png");
  await pageCheck("/knowledge/search", "混合检索 + 特征精排", "retrieval-search.png");
  await pageCheck("/multimodal", "跨模态检索", "multimodal-cross-modal.png");
  const failed = consoleErrors.length || networkFailures.length || results.some((item) => !item.expected_text_found);
  writeResult(failed ? "FAILED" : "PASSED", { credential_values_output: false });
  return failed ? 1 : 0;
}

main().then((code) => { client?.ws?.close(); browser?.kill(); process.exitCode = code; }).catch((error) => {
  writeResult("FAILED", { error: `${error.name}: ${error.message}`, credential_values_output: false });
  client?.ws?.close(); browser?.kill(); process.exitCode = 1;
});
