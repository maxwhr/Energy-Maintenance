import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE_URL = (process.env.TASK21C_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const ADMIN_USERNAME = process.env.TASK21C_ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.TASK21C_ADMIN_PASSWORD || "admin123456";
const VIEWER_USERNAME = process.env.TASK21C_VIEWER_USERNAME || "viewer";
const VIEWER_PASSWORD = process.env.TASK21C_VIEWER_PASSWORD || "admin123456";
const CDP_PORT = Number(process.env.TASK21C_CDP_PORT || 9223);
const RUN_ID = `Task21C_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const RUNTIME_DIR = path.resolve(process.cwd(), "..", ".runtime", "task21c");
const RESULT_FILE = path.join(RUNTIME_DIR, "browser_click_result.json");
const SAMPLE_FILE = path.join(RUNTIME_DIR, "task21c_pv_inverter_sample.txt");

const browserCandidates = [
  process.env.TASK21C_BROWSER_PATH,
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
let currentStep = "startup";

function record(name, status, notes = "") {
  results.push({ name, status, notes });
  const marker = status === "passed" ? "[PASS]" : status === "blocked" ? "[BLOCKED]" : "[FAIL]";
  console.log(`${marker} ${name}${notes ? ` - ${notes}` : ""}`);
}

function step(name) {
  currentStep = name;
  console.log(`[STEP] ${name}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(fn, timeoutMs = 15000, intervalMs = 300) {
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

async function fetchJson(url, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
    this.ws.addEventListener("message", (event) => this.onMessage(event));
  }

  async ready() {
    await new Promise((resolve, reject) => {
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
        requestId: msg.params.requestId,
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

  async once(method, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`CDP event timeout: ${method}`)), timeoutMs);
      const listeners = this.events.get(method) || [];
      listeners.push((params) => {
        clearTimeout(timer);
        resolve(params);
      });
      this.events.set(method, listeners);
    });
  }

  async eval(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      const details = result.exceptionDetails;
      throw new Error(
        [
          details.text || "Evaluation failed",
          details.exception?.description || "",
          details.url ? `url=${details.url}` : "",
          details.lineNumber != null ? `line=${details.lineNumber}` : "",
          details.columnNumber != null ? `column=${details.columnNumber}` : "",
        ].filter(Boolean).join(" | "),
      );
    }
    return result.result?.value;
  }

  async navigate(pagePath) {
    const url = pagePath.startsWith("http") ? pagePath : `${BASE_URL}${pagePath}`;
    await this.send("Page.navigate", { url });
    await sleep(800);
    await waitFor(async () => {
      const ready = await this.eval("document.readyState");
      return ready === "complete" || ready === "interactive";
    }, 15000);
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
    const findByText = (selector, texts) => {
      const list = Array.from(document.querySelectorAll(selector)).filter(visible);
      return list.find((el) => texts.some((text) => labelText(el).includes(text)));
    };
    ${body}
  })()`;
}

async function clickByText(texts) {
  const textList = Array.isArray(texts) ? texts : [texts];
  const res = await cdp.eval(domScript(`
    const el = findByText("button,a,[role='button'],summary,input[type='submit']", ${JSON.stringify(textList)});
    if (!el) return { ok: false, text: ${JSON.stringify(textList)} };
    el.scrollIntoView({ block: "center", inline: "center" });
    el.click();
    return { ok: true, text: labelText(el) };
  `));
  await sleep(900);
  return res;
}

async function clickFirstSubmit() {
  const res = await cdp.eval(domScript(`
    const el = Array.from(document.querySelectorAll("form button[type='submit'], form input[type='submit']")).filter(visible)[0];
    if (!el) return { ok: false };
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

async function textIncludes(texts) {
  const textList = Array.isArray(texts) ? texts : [texts];
  const body = await cdp.eval("document.body ? document.body.innerText : ''");
  return textList.some((text) => body.includes(text));
}

async function bodyText() {
  return cdp.eval("document.body ? document.body.innerText : ''");
}

async function currentPath() {
  return cdp.eval("location.pathname");
}

async function waitForAnyText(texts, timeoutMs = 15000) {
  return waitFor(() => textIncludes(texts), timeoutMs);
}

async function assertPage(pathname, expectedTexts = []) {
  await cdp.navigate(pathname);
  const text = await bodyText();
  if (!text || text.trim().length < 40) {
    throw new Error(`${pathname} rendered blank or too little text`);
  }
  for (const expected of expectedTexts) {
    if (!text.includes(expected)) throw new Error(`${pathname} missing text: ${expected}`);
  }
  return text;
}

async function login(username, password, expectedRoleText) {
  step(`login ${username}`);
  await cdp.navigate("/login");
  await fillBySelector("input[autocomplete='username'], input:not([type='password'])", username);
  await fillBySelector("input[type='password']", password);
  const clicked = await clickFirstSubmit();
  if (!clicked.ok) throw new Error("login submit button not found");
  try {
    await waitFor(async () => {
      const pathName = await currentPath();
      const text = await bodyText();
      return pathName !== "/login" && (text.includes(expectedRoleText) || text.includes("运行总览") || text.includes("工作台"));
    }, 15000);
  } catch (error) {
    const pathName = await currentPath();
    const text = await bodyText();
    throw new Error(`login did not leave /login; current=${pathName}; text=${text.slice(0, 500)}`);
  }
}

async function logoutLocal() {
  await cdp.eval("try { localStorage.clear(); sessionStorage.clear(); } catch (error) {} true");
}

async function runAdminChecks() {
  step("admin checks");
  await logoutLocal();
  await login(ADMIN_USERNAME, ADMIN_PASSWORD, "管理员");
  record("admin browser login", "passed", "login form submitted and dashboard restored");

  const routes = [
    ["/dashboard", ["运行总览"]],
    ["/device/inventory", ["设备台账"]],
    ["/device/models", ["产品系列"]],
    ["/device/alarms", ["告警"]],
    ["/knowledge/documents", ["知识文档", "上传并解析"]],
    ["/knowledge/contributions", ["一线经验"]],
    ["/knowledge/graph", ["知识"]],
    ["/knowledge/search", ["知识检索"]],
    ["/knowledge/cases", ["故障案例"]],
    ["/assistant/chat", ["检修问答"]],
    ["/assistant/history", ["问答记录"]],
    ["/diagnosis", ["故障诊断"]],
    ["/sop", ["作业规程"]],
    ["/workorder/list", ["检修任务"]],
    ["/workorder/create", ["新建任务"]],
    ["/trace", ["记录追溯"]],
    ["/review", ["知识审核"]],
    ["/review/corrections", ["人工修正"]],
    ["/model-service", ["模型服务"]],
    ["/media", ["媒体"]],
    ["/system", ["系统状态"]],
    ["/system/users", ["用户管理"]],
  ];
  for (const [route, expected] of routes) {
    step(`open ${route}`);
    await assertPage(route, expected);
    record(`open page ${route}`, "passed");
  }

  step("knowledge upload");
  await cdp.navigate("/knowledge/documents");
  const fileSet = await setFileInput(SAMPLE_FILE);
  if (!fileSet) throw new Error("knowledge file input not found");
  await fillByLabel("文档标题", `${RUN_ID} 浏览器上传样例`);
  await fillByLabel("来源", "Task21C browser click acceptance");
  let clicked = await clickByText("上传并解析");
  if (!clicked.ok) throw new Error("knowledge upload button not found");
  await waitForAnyText(["解析状态", `${RUN_ID} 浏览器上传样例`, "切片"], 25000);
  record("knowledge upload form submit", "passed", "file input set through CDP and submit button clicked");
  clicked = await clickByText("查看切片");
  if (!clicked.ok) throw new Error("view chunks button not found");
  await waitForAnyText(["切片预览", "逆变器"], 15000);
  record("knowledge chunk preview button", "passed", "real chunk preview opened");

  step("knowledge search");
  await cdp.navigate("/knowledge/search");
  await fillBySelector("textarea", "逆变器告警后如何排查？请给出安全注意事项和来源。");
  clicked = await clickByText(["检索", "提交", "查询"]);
  if (!clicked.ok) throw new Error("knowledge search submit button not found");
  await waitForAnyText(["trace_id", "参考", "来源", "建议"], 25000);
  record("knowledge retrieval form submit", "passed", "query submitted and answer/source area rendered");

  step("assistant chat");
  await cdp.navigate("/assistant/chat");
  await fillBySelector("textarea", "SUN2000 绝缘阻抗低告警如何排查？");
  clicked = await clickByText(["发送", "提交", "检索", "提问"]);
  if (!clicked.ok) throw new Error("assistant chat submit button not found");
  await waitForAnyText(["trace_id", "置信度", "参考", "来源"], 25000);
  record("assistant chat form submit", "passed");

  step("diagnosis submit");
  await cdp.navigate("/diagnosis");
  await fillByLabel("告警代码", "Task21C-ALM");
  await fillBySelector("textarea", "华为 SUN2000 逆变器出现绝缘阻抗低告警，并网前自检失败，需要现场排查。");
  clicked = await clickByText("提交诊断");
  if (!clicked.ok) throw new Error("diagnosis submit button not found");
  await waitForAnyText(["可能原因", "排查步骤", "安全注意事项", "推荐处理措施", "trace_id"], 25000);
  record("diagnosis form submit", "passed");

  step("sop generate and template");
  await cdp.navigate("/sop");
  clicked = await clickByText("生成规程建议");
  if (!clicked.ok) throw new Error("SOP generate button not found");
  await waitForAnyText(["生成结果", "步骤", "安全要求", "参考来源"], 25000);
  record("SOP generate button", "passed");
  await fillBySelector("input[placeholder*='模板标题']", `${RUN_ID} 低绝缘阻抗排查规程`);
  await fillBySelector("textarea[placeholder*='核心作业步骤']", "断开并确认直流侧安全，检查组串绝缘阻抗和端子接线。");
  await fillBySelector("textarea[placeholder*='安全要求']", "必须佩戴绝缘防护用品，执行停电验电和挂牌流程。");
  clicked = await clickByText("创建模板");
  if (!clicked.ok) throw new Error("SOP create template button not found");
  await waitForAnyText([`${RUN_ID} 低绝缘阻抗排查规程`, "规程模板"], 25000);
  record("SOP template create form", "passed");

  step("workorder create");
  await cdp.navigate("/workorder/create");
  await fillByLabel("任务标题", `${RUN_ID} 逆变器告警排查任务`);
  await fillByLabel("告警代码", "Task21C-WO");
  await fillBySelector("textarea", "浏览器验收创建的检修任务：逆变器告警、功率下降，需现场确认。");
  clicked = await clickByText("创建任务");
  if (!clicked.ok) throw new Error("workorder create button not found");
  await waitForAnyText(["任务详情", `${RUN_ID} 逆变器告警排查任务`, "故障"], 25000);
  record("workorder create form", "passed");

  step("device inventory create");
  await cdp.navigate("/device/inventory");
  await fillByLabel("设备名称", `${RUN_ID} SUN2000 浏览器台账`);
  await fillByLabel("设备编号", `EM-${RUN_ID}`);
  await fillBySelector("input[placeholder*='型号']", "SUN2000-50KTL-M3");
  await fillBySelector("input[placeholder*='电站名称']", "Task21C 光伏电站");
  await fillBySelector("input[placeholder*='安装位置']", "逆变器室 01");
  clicked = await clickByText("保存台账");
  if (!clicked.ok) throw new Error("device save button not found");
  await waitForAnyText([`${RUN_ID} SUN2000 浏览器台账`, "详情", "编辑"], 25000);
  record("device inventory create form", "passed");
  clicked = await clickByText("详情");
  if (!clicked.ok) throw new Error("device detail button not found");
  await waitForAnyText(["设备详情", "新增维修履历"], 15000);
  record("device detail button", "passed");

  step("knowledge contribution");
  await cdp.navigate("/knowledge/contributions");
  await fillByLabel("标题", `${RUN_ID} 一线经验`);
  await fillBySelector("textarea[placeholder*='现场现象']", "逆变器出现告警，现场排查发现直流端子潮湿。");
  await fillBySelector("textarea[placeholder*='排查步骤']", "核对告警，停电验电，检查端子、线缆和绝缘阻抗。");
  await fillBySelector("textarea[placeholder*='最终定位']", "疑似端子受潮导致绝缘下降。");
  await fillBySelector("textarea[placeholder*='恢复措施']", "清洁端子并复测绝缘，确认并网正常。");
  clicked = await clickByText("保存草稿");
  if (!clicked.ok) throw new Error("contribution save draft button not found");
  await waitForAnyText([`${RUN_ID} 一线经验`, "草稿"], 25000);
  record("knowledge contribution draft form", "passed");

  step("model gateway");
  await cdp.navigate("/model-service");
  await fillBySelector("input[placeholder*='测试内容']", "返回规则模型连通状态");
  clicked = await clickByText("测试调用");
  if (!clicked.ok) throw new Error("model test button not found");
  await waitForAnyText(["响应", "provider", "规则兜底模型", "model"], 25000);
  record("model gateway test form", "passed");

  step("system user create");
  await cdp.navigate("/system/users");
  await fillByLabel("用户名", `${RUN_ID.toLowerCase()}_viewer`);
  await fillBySelector("input[placeholder*='华为逆变器检修专家']", "Task21C 只读验收用户");
  await fillBySelector("input[type='password']", "task21cPass123");
  clicked = await clickByText("创建用户");
  if (!clicked.ok) throw new Error("create user button not found");
  await waitForAnyText([`${RUN_ID.toLowerCase()}_viewer`, "Task21C 只读验收用户"], 25000);
  record("system user create form", "passed");

  step("system status refresh");
  await cdp.navigate("/system");
  clicked = await clickByText("刷新");
  if (!clicked.ok) throw new Error("system refresh button not found");
  await waitForAnyText(["数据库", "后端", "知识库"], 15000);
  record("system refresh button", "passed");
}

async function runViewerChecks() {
  step("viewer checks");
  await logoutLocal();
  await login(VIEWER_USERNAME, VIEWER_PASSWORD, "只读用户");
  record("viewer browser login", "passed");
  await assertPage("/dashboard", ["运行总览"]);
  await assertPage("/workorder/list", ["检修任务"]);
  const writeButtonHidden = !(await textIncludes(["新建任务", "创建任务", "保存台账", "模型服务"]));
  if (!writeButtonHidden) throw new Error("viewer sees write-only labels on read-only pages");
  record("viewer readonly navigation", "passed", "dashboard/workorder available without write entry");
  await cdp.navigate("/review");
  await waitFor(async () => {
    const pathName = await currentPath();
    const text = await bodyText();
    return pathName === "/403" || text.includes("无权访问") || text.includes("权限不足");
  }, 15000);
  record("viewer forced /review guard", "passed", "redirected or forbidden page shown");
}

async function main() {
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  fs.writeFileSync(
    SAMPLE_FILE,
    [
      "Task21C photovoltaic inverter maintenance sample.",
      "Huawei SUN2000 inverter alarm troubleshooting requires safety isolation before inspection.",
      "When an inverter reports an insulation resistance alarm, verify DC string insulation, cable terminals, moisture, and grounding.",
      "Sungrow SG series alarm handling should record alarm code, operating state, and recovery verification.",
      "安全要求：现场检修前必须断开直流侧和交流侧，执行验电、挂牌和绝缘防护。",
    ].join("\n"),
    "utf8",
  );

  const health = await fetchJson(`${BASE_URL}/api/health`);
  if (health?.data?.name !== "Energy-Maintenance") {
    throw new Error(`${BASE_URL} is not Energy-Maintenance`);
  }
  record("backend identity", "passed", `${BASE_URL} reports Energy-Maintenance`);

  const browserPath = findBrowserPath();
  if (!browserPath) throw new Error("No Chrome or Edge executable found");
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "em-task21c-profile-"));
  browserProcess = spawn(browserPath, [
    "--headless=new",
    `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${userDataDir}`,
    "--disable-gpu",
    "--remote-allow-origins=*",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1440,1000",
    "about:blank",
  ], { stdio: "ignore" });

  const version = await waitFor(() => fetchJson(`http://127.0.0.1:${CDP_PORT}/json/version`, 2000), 15000);
  const tabs = await fetchJson(`http://127.0.0.1:${CDP_PORT}/json`);
  const tab = tabs.find((item) => item.type === "page") || tabs[0];
  cdp = new CDPClient(tab.webSocketDebuggerUrl || version.webSocketDebuggerUrl);
  await cdp.ready();
  await Promise.all([
    cdp.send("Page.enable"),
    cdp.send("Runtime.enable"),
    cdp.send("DOM.enable"),
    cdp.send("Network.enable"),
    cdp.send("Log.enable"),
  ]);
  record("headless browser startup", "passed", browserPath);

  await runAdminChecks();
  await runViewerChecks();

  const criticalConsoleErrors = consoleErrors.filter((item) => !String(item.text || "").includes("favicon"));
  if (criticalConsoleErrors.length) {
    record("frontend runtime error check", "failed", JSON.stringify(criticalConsoleErrors.slice(0, 3)));
  } else {
    record("frontend runtime error check", "passed");
  }

  const criticalNetworkFailures = networkFailures.filter((item) => !["Image", "Font"].includes(item.type));
  if (criticalNetworkFailures.length) {
    record("network failure check", "failed", JSON.stringify(criticalNetworkFailures.slice(0, 3)));
  } else {
    record("network failure check", "passed");
  }
}

try {
  await main();
} catch (error) {
  record("task21c browser acceptance", "failed", error instanceof Error ? error.message : String(error));
} finally {
  if (cdp) cdp.close();
  if (browserProcess && !browserProcess.killed) browserProcess.kill();
  const failed = results.filter((item) => item.status === "failed");
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  fs.writeFileSync(
    RESULT_FILE,
    JSON.stringify(
      {
        base_url: BASE_URL,
        run_id: RUN_ID,
        result: failed.length ? "failed" : "passed",
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
  process.exit(failed.length ? 1 : 0);
}
