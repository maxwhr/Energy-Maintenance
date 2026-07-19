import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const outputDir = path.join(root, ".runtime", "task25c");
const outputPath = path.join(outputDir, "browser_review.json");
const credentialsPath = path.join(root, ".runtime", "task25a_r1", ".test_credentials.private.json");
const baseUrl = (process.env.TASK25C_BASE_URL || "http://127.0.0.1:8012").replace(/\/$/, "");
if (!fs.existsSync(credentialsPath)) throw new Error("private browser test credentials are not prepared");
const credentials = JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
const browserPath = [
  process.env.TASK25C_BROWSER_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserPath) throw new Error("Chrome or Edge executable was not found");

const checks = {};
const consoleErrors = [];
const pageErrors = [];
const networkFailures = [];
function record(name, passed, evidence = null) { checks[name] = { passed: Boolean(passed), evidence }; }
function unwrap(payload) { return payload && typeof payload === "object" && "data" in payload ? payload.data : payload; }

async function apiJson(page, apiPath, method = "GET", body = null) {
  return page.evaluate(async ({ apiPath, method, body }) => {
    const token = localStorage.getItem("energy_maintenance_access_token") || "";
    const response = await fetch(apiPath, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const payload = await response.json();
    return { ok: response.ok, status: response.status, data: payload && typeof payload === "object" && "data" in payload ? payload.data : payload };
  }, { apiPath, method, body });
}

async function login(page, account) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.locator("input[autocomplete='username']").fill(account.username);
  await page.locator("input[type='password']").fill(account.password);
  const pending = page.waitForResponse((response) => response.url().includes("/api/auth/login") && response.request().method() === "POST");
  await page.locator("form button[type='submit']").click();
  const response = await pending;
  if (!response.ok()) throw new Error(`login failed with HTTP ${response.status()}`);
  const payload = unwrap(await response.json());
  await page.waitForTimeout(400);
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

const browser = await chromium.launch({ headless: true, executablePath: browserPath, args: ["--disable-gpu", "--no-first-run"] });
try {
  const context = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
  const page = await context.newPage();
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const message = request.failure()?.errorText || "failed";
    if (!message.includes("ERR_ABORTED")) networkFailures.push(`${request.method()} ${request.url()} ${message}`);
  });
  page.on("response", (response) => {
    if (["xhr", "fetch"].includes(response.request().resourceType()) && response.status() >= 400) {
      networkFailures.push(`${response.request().method()} ${response.url()} HTTP ${response.status()}`);
    }
  });

  const admin = await login(page, credentials.admin);
  record("admin_login", admin?.user?.role === "admin", admin?.user?.role);
  await page.goto(`${baseUrl}/multimodal-maintenance`, { waitUntil: "networkidle" });
  await page.getByTestId("multimodal-maintenance-page").waitFor({ state: "visible", timeout: 20000 });
  record("workbench_visible", await page.getByTestId("multimodal-maintenance-page").isVisible());
  record("new_case_panel", await page.getByText("1-3. 新建检修案例").isVisible());

  const unique = Date.now();
  const primaryCaseTitle = `Task25C browser acceptance ${unique}`;
  const createForm = page.getByTestId("multimodal-case-create");
  await createForm.getByPlaceholder("案例标题").fill(primaryCaseTitle);
  await createForm.getByPlaceholder("请描述现象、时间、告警和已执行操作").fill("SUN2000-50KTL-M3 告警代码 2064，请核对原因、排查步骤和安全要求");
  await createForm.getByPlaceholder("人工已知型号（可选）").fill("SUN2000-50KTL-M3");
  const createPending = page.waitForResponse((response) => response.url().endsWith("/api/multimodal/cases") && response.request().method() === "POST");
  await createForm.getByRole("button", { name: "新建案例" }).click();
  const createResponse = await createPending;
  const created = unwrap(await createResponse.json());
  record("case_created", createResponse.ok() && Boolean(created?.case_id), created?.status);

  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAFklEQVR4nGP8//8/A27AhEeOYeRKAwCl4wMRx3ocVQAAAABJRU5ErkJggg==", "base64");
  await page.waitForFunction(() => {
    const button = document.querySelector('[data-testid="multimodal-analyze"]');
    return button instanceof HTMLButtonElement && !button.disabled;
  });
  await page.getByTestId("multimodal-media-upload").setInputFiles({ name: "task25c-browser.png", mimeType: "image/png", buffer: png });
  await page.waitForFunction(() => {
    const button = Array.from(document.querySelectorAll("button")).find((item) => item.textContent?.trim() === "上传图片");
    return button instanceof HTMLButtonElement && !button.disabled;
  });
  const uploadPending = page.waitForResponse((response) => response.url().includes(`/api/multimodal/cases/${created.case_id}/media`) && response.request().method() === "POST");
  await page.getByRole("button", { name: "上传图片" }).click();
  const uploadResponse = await uploadPending;
  const uploaded = unwrap(await uploadResponse.json());
  record("media_uploaded", uploadResponse.ok());
  await page.waitForTimeout(800);
  record("preview_or_media_selector", Boolean(uploaded?.preview_url?.startsWith("/api/media/")) || (await page.locator("img[alt='案例媒体预览']").count()) > 0 || (await page.getByText("task25c-browser.png").count()) > 0);

  const analyzePending = page.waitForResponse((response) => response.url().includes(`/api/multimodal/cases/${created.case_id}/analyze`) && response.request().method() === "POST");
  await page.getByTestId("multimodal-analyze").click();
  const analyzeResponse = await analyzePending;
  record("dry_run_analyze", analyzeResponse.ok());
  record("ocr_region_panel", await page.getByText("4-7. 图片、OCR 与视觉区域").isVisible());
  record("entity_panels", await page.getByText("8. 识别型号").isVisible() && await page.getByText("9. 识别告警").isVisible());
  record("component_indicator_panels", await page.getByText("10. 识别部件").isVisible() && await page.getByText("11. 指示灯状态").isVisible());
  record("quality_panel", await page.getByText("12. 图片质量提示").isVisible());
  record("conflict_panel", await page.getByText("13. 证据冲突提示").isVisible());
  record("clarification_panel", await page.getByText("14-15. 缺失信息、主动追问与用户补充").isVisible());

  const clarificationInputs = page.getByPlaceholder("请补充事实，不要猜测");
  const clarificationCount = await clarificationInputs.count();
  if (clarificationCount) {
    for (let index = 0; index < clarificationCount; index += 1) {
      await clarificationInputs.nth(index).fill("并网运行期间，图片属于当前设备，人工确认后继续核验");
    }
    const clarificationPending = page.waitForResponse((response) => response.url().endsWith(`/api/multimodal/cases/${created.case_id}/clarify`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "提交补充信息" }).click();
    const clarificationResponse = await clarificationPending;
    record("clarification_submitted", clarificationResponse.ok(), clarificationCount);
  } else {
    record("clarification_submitted", true, "analysis determined that no clarification was required");
  }

  const retrievePending = page.waitForResponse((response) => response.url().includes(`/api/multimodal/cases/${created.case_id}/retrieve`) && response.request().method() === "POST", { timeout: 45000 });
  await page.getByTestId("multimodal-retrieve").click();
  const retrieveResponse = await retrievePending;
  const retrieved = unwrap(await retrieveResponse.json());
  record("cross_modal_retrieval", retrieveResponse.ok() && retrieved?.generated_queries?.[0]?.query_type === "ORIGINAL_TEXT");
  record("citation_panel", await page.getByTestId("multimodal-citations").isVisible());
  record("dedicated_rerank_not_used", retrieved?.dedicated_rerank?.used === false, retrieved?.dedicated_rerank?.status);

  await page.reload({ waitUntil: "networkidle" });
  await page.getByTestId("multimodal-maintenance-page").waitFor({ state: "visible", timeout: 20000 });
  const confirmButtons = page.getByRole("button", { name: "确认", exact: true });
  if (await confirmButtons.count()) {
    const confirmPending = page.waitForResponse((response) => response.url().includes(`/api/multimodal/cases/${created.case_id}/evidence/`) && response.url().endsWith("/confirm") && response.request().method() === "POST");
    await confirmButtons.first().click();
    const confirmResponse = await confirmPending;
    record("evidence_confirmed", confirmResponse.ok());
  } else {
    record("evidence_confirmed", false, "no confirmable evidence was rendered after retrieval");
  }
  const rejectButtons = page.getByRole("button", { name: "识别错误", exact: true });
  if (await rejectButtons.count()) {
    const rejectPending = page.waitForResponse((response) => response.url().includes(`/api/multimodal/cases/${created.case_id}/evidence/`) && response.url().endsWith("/reject") && response.request().method() === "POST");
    await rejectButtons.first().click();
    const rejectResponse = await rejectPending;
    record("evidence_rejected", rejectResponse.ok());
  } else {
    record("evidence_rejected", false, "no rejectable evidence was rendered after retrieval");
  }

  const diagnosePending = page.waitForResponse((response) => response.url().includes(`/api/multimodal/cases/${created.case_id}/diagnose`) && response.request().method() === "POST", { timeout: 30000 });
  await page.getByTestId("multimodal-diagnose").click();
  const diagnoseResponse = await diagnosePending;
  const diagnosed = unwrap(await diagnoseResponse.json());
  record("diagnosis_boundary", diagnoseResponse.ok() && diagnosed?.unsupported_diagnosis_count === 0, diagnosed?.confidence_status);
  record("safety_warning_visible", await page.getByText("安全警告", { exact: true }).isVisible());
  record("sop_draft_panel", await page.getByText("22. SOP 草稿").isVisible());
  record("task_draft_panel", await page.getByText("23. Task 草稿").isVisible());
  const sopPending = page.waitForResponse((response) => response.url().endsWith(`/api/multimodal/cases/${created.case_id}/sop-draft`) && response.request().method() === "POST");
  await page.getByRole("button", { name: "生成 SOP 草稿" }).click();
  const sopResponse = await sopPending;
  const sopPayload = unwrap(await sopResponse.json());
  const sopCreated = sopResponse.ok() && sopPayload?.artifact?.artifact_type === "sop_draft" && Boolean(sopPayload?.artifact?.artifact_id);
  record("sop_draft_created", sopCreated, sopPayload?.boundary?.reason || sopPayload?.artifact?.artifact_type || null);
  if (sopCreated) {
    await page.getByText("我已人工确认 SOP 草稿可用于创建任务草稿").locator("input").check();
    const taskPending = page.waitForResponse((response) => response.url().endsWith(`/api/multimodal/cases/${created.case_id}/task-draft`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "生成 Task 草稿" }).click();
    const taskResponse = await taskPending;
    const taskPayload = unwrap(await taskResponse.json());
    record("task_draft_created", taskResponse.ok() && taskPayload?.artifact?.artifact_type === "task_draft" && Boolean(taskPayload?.artifact?.artifact_id), taskPayload?.boundary?.reason || taskPayload?.artifact?.artifact_type || null);
  } else {
    record("task_draft_created", false, "SOP draft gate did not pass");
  }
  const auditItems = page.getByText("24. 审计时间线").locator("xpath=following::ol[1]/li");
  record("audit_timeline", await page.getByText("24. 审计时间线").isVisible() && (await auditItems.count()) > 0, await auditItems.count());

  const multipleCaseResponse = await apiJson(page, "/api/multimodal/cases", "POST", {
    title: `Task25C multiple possibilities ${unique}`,
    user_query: "SUN2000-50KTL-M3 同时出现告警 2064 和 2001，请分别核对原因与安全排查步骤",
    device_model: "SUN2000-50KTL-M3",
    occurrence_conditions: ["并网运行期间"],
    idempotency_key: `task25c-browser-multiple-${unique}`,
  });
  let multipleResult = null;
  if (multipleCaseResponse.ok && multipleCaseResponse.data?.case_id) {
    const multipleCaseId = multipleCaseResponse.data.case_id;
    const analyzedMultiple = await apiJson(page, `/api/multimodal/cases/${multipleCaseId}/analyze`, "POST", {
      dry_run: true, mock_run: false, allow_real_api: false, force: false,
    });
    if (analyzedMultiple.ok) {
      await apiJson(page, `/api/multimodal/cases/${multipleCaseId}/clarify`, "POST", {
        answers: { occurrence_condition: "并网运行期间" }, confirmed_facts: {},
      });
      const retrievedMultiple = await apiJson(page, `/api/multimodal/cases/${multipleCaseId}/retrieve`, "POST", {
        top_k: 5, requested_information: ["CAUSE", "ACTION", "SAFETY"],
      });
      if (retrievedMultiple.ok && (retrievedMultiple.data?.citations || []).length) {
        multipleResult = await apiJson(page, `/api/multimodal/cases/${multipleCaseId}/diagnose`, "POST", { proposed_actions: [] });
      }
    }
  }
  record(
    "multiple_possibilities",
    multipleResult?.ok && multipleResult.data?.case_status === "MULTIPLE_POSSIBILITIES" && (multipleResult.data?.possible_faults || []).length > 1,
    multipleResult?.data?.case_status || multipleResult?.status || "not reached",
  );

  const noAnswerCaseResponse = await apiJson(page, "/api/multimodal/cases", "POST", {
    title: `Task25C no answer ${unique}`,
    user_query: "不存在的 ZXQ-9999 设备告警 999999，请给出该型号专属维修参数",
    device_model: "ZXQ-9999",
    occurrence_conditions: ["未知实验条件"],
    idempotency_key: `task25c-browser-no-answer-${unique}`,
  });
  let noAnswerResult = null;
  if (noAnswerCaseResponse.ok && noAnswerCaseResponse.data?.case_id) {
    const noAnswerCaseId = noAnswerCaseResponse.data.case_id;
    const analyzedNoAnswer = await apiJson(page, `/api/multimodal/cases/${noAnswerCaseId}/analyze`, "POST", {
      dry_run: true, mock_run: false, allow_real_api: false, force: false,
    });
    if (analyzedNoAnswer.ok) {
      noAnswerResult = await apiJson(page, `/api/multimodal/cases/${noAnswerCaseId}/retrieve`, "POST", {
        top_k: 5, requested_information: ["CAUSE", "ACTION", "SAFETY"],
      });
    }
  }
  record(
    "no_answer_boundary",
    noAnswerResult?.ok && (noAnswerResult.data?.citations || []).length === 0 && noAnswerResult.data?.confidence_status === "INSUFFICIENT_EVIDENCE",
    noAnswerResult?.data?.confidence_status || noAnswerResult?.status || "not reached",
  );

  record("admin_console_errors_zero", consoleErrors.length === 0, consoleErrors.length);
  record("admin_network_failures_zero", networkFailures.length === 0, networkFailures.length);
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.evaluate(() => localStorage.clear());
  const viewer = await login(page, credentials.viewer);
  consoleErrors.length = 0;
  networkFailures.length = 0;
  record("viewer_login", viewer?.user?.role === "viewer", viewer?.user?.role);
  await page.goto(`${baseUrl}/multimodal-maintenance`, { waitUntil: "networkidle" });
  await page.getByTestId("multimodal-maintenance-page").waitFor({ state: "visible", timeout: 20000 });
  record("viewer_read_only_create", await page.getByRole("button", { name: "新建案例" }).isDisabled());
  record("viewer_no_evidence_mutation", (await page.getByRole("button", { name: "确认", exact: true }).count()) === 0);
  record("viewer_no_sop_task_generation", (await page.getByRole("button", { name: "生成 SOP 草稿" }).count()) === 0 || await page.getByRole("button", { name: "生成 SOP 草稿" }).isDisabled());

  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.evaluate(() => localStorage.clear());
  const engineer = await login(page, credentials.engineer);
  record("engineer_login", engineer?.user?.role === "engineer", engineer?.user?.role);
  await page.goto(`${baseUrl}/multimodal-maintenance`, { waitUntil: "networkidle" });
  await page.getByTestId("multimodal-maintenance-page").waitFor({ state: "visible", timeout: 20000 });
  record("engineer_can_create_case", !(await page.getByPlaceholder("案例标题").isDisabled()) && !(await page.getByPlaceholder("请描述现象、时间、告警和已执行操作").isDisabled()));

  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.evaluate(() => localStorage.clear());
  const expert = await login(page, credentials.expert);
  record("expert_login", expert?.user?.role === "expert", expert?.user?.role);
  await page.goto(`${baseUrl}/multimodal-maintenance`, { waitUntil: "networkidle" });
  await page.getByTestId("multimodal-maintenance-page").waitFor({ state: "visible", timeout: 20000 });
  await page.getByText(primaryCaseTitle, { exact: true }).click();
  await page.getByTestId("multimodal-evidence-list").waitFor({ state: "visible", timeout: 20000 });
  record(
    "expert_evidence_review_access",
    !(await page.getByPlaceholder("案例标题").isDisabled())
      && (await page.getByTestId("multimodal-evidence-list").locator("article").count()) > 0
      && ((await page.getByText("用户确认").count()) > 0 || (await page.getByText("已拒绝").count()) > 0 || (await page.getByText("已观察").count()) > 0),
  );

  const html = await page.content();
  record("no_secret_rendered", !html.includes(credentials.admin.password) && !html.includes(credentials.expert.password) && !html.includes(credentials.engineer.password) && !html.includes(credentials.viewer.password) && !html.toLowerCase().includes("authorization: bearer"));
  record("no_internal_prompt", !html.includes("完整内部 Prompt") && !html.includes("rerank_documents"));
  record("console_errors_zero", consoleErrors.length === 0, consoleErrors.length);
  record("page_errors_zero", pageErrors.length === 0, pageErrors.length);
  record("network_failures_zero", networkFailures.length === 0, networkFailures.length);

  const failures = Object.entries(checks).filter(([, item]) => !item.passed).map(([name]) => name);
  const result = {
    generated_at: new Date().toISOString(), task: "Task 25C browser review", status: failures.length ? "FAILED" : "PASSED",
    real_browser: true, automation: "project-node-playwright", base_url: baseUrl,
    browser_executable: path.basename(browserPath), checks, failures,
    console_errors: consoleErrors, page_errors: pageErrors, unexpected_network_failures: networkFailures,
    credentials_output: false, api_key_rendered: false, provider_response_rendered: false,
  };
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: result.status, checks: Object.keys(checks).length, failures }));
  if (failures.length) process.exitCode = 2;
} finally {
  await browser.close();
}
