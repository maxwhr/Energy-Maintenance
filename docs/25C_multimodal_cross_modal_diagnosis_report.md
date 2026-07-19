# Task 25C 多模态跨模态诊断统一报告

生成时间：2026-07-14T18:39:49.602684+00:00

## 1. 当前系统基线

- 中文正式工程知识文档：16
- 中文 active chunks：1262
- Semantic Unit V2：2508
- 基线向量 Partition：`{"pilot_r2": 1262, "pilot_r3_semantic": 416, "pilot_r4_grounded": 1289, "pilot_r5_query_aware": 2508}`
- 基线 Alembic：`20260712_0013 (head)`；本任务目标 head 为 `20260712_0014`。

## 2. R6 专用重排延后状态

`DEFERRED_QWEN3_RERANK_CONFIG`。Task 25C 检索链路没有调用 Qwen3 rerank、R6 Canary 或 Formal，使用确定性降级链路，不声称 RAG 专用重排正式质量通过。Task 25C 基线之后曾按用户单独的 R6 指令刷新 R6 Probe/浏览器/Smoke 工件，但配置门禁在网络前停止，Qwen3 真实调用仍为 0；原冻结 hash 漂移保留在 regression 证据中，语义边界复核=True。

## 3. 多模态案例模型

已落地 `MultimodalMaintenanceCase`、Evidence、Conflict、Diagnostic Hypothesis 四张表及状态机。当前数据库：cases=27、media links=12、evidence=156、regions=0、conflicts=14、hypotheses=25。

## 4. 媒体安全

状态：`PASS`。覆盖 MIME/扩展名/文件头校验、像素与解压炸弹限制、随机文件名、路径边界、SHA-256、去重、EXIF 清理和安全重编码。

## 5. 图片预处理

预处理证据：`{"source_unchanged": true, "variants": 6, "hashes_valid": true, "ocr_ready": true, "vision_ready": true}`。原图不覆盖，派生版本保留 hash 和变换参数，无 GPU/CUDA 依赖。

## 6. OCR 证据

确定性 OCR 区域归一、坐标、block hash、型号/告警/参数/通信状态提取已完成。真实 Probe：`SAFE_FALLBACK`；原因：`provider unavailable or rejected request`；外部调用=False。

## 7. 视觉证据

视觉结构化输出只允许可观察候选，始终保持 INFERRED/LOW_CONFIDENCE，禁止直接诊断和维修步骤。真实 Probe：`SAFE_FALLBACK`；原因：`provider unavailable or rejected request`；外部调用=False。

## 8. 区域级证据

Evidence 保存 `region_id`、bounding box、source image、locator、attributes 和 confidence；前端支持区域框、证据点击、确认和拒绝。当前持久化 region 数=0；因授权媒体不足且真实 OCR/视觉 Provider 在配置预检处安全降级，本轮不能用 0 个真实区域声称区域识别质量达标。

## 9. 实体解析

解析优先级为用户确认、绑定设备、高置信 OCR、视觉推断和案例提示；无法确定时不默认 `pv_inverter`，支持 SUN2000/LUNA2000/SmartLogger/SG。

## 10. 冲突处理

型号、告警、设备绑定、指示灯和跨 Provider 差异以独立 Conflict 记录保存，高风险冲突不得由模型自动消除。

## 11. 主动追问

追问来自固定安全模板，覆盖模糊图片、完整型号、告警码、完整屏幕、指示灯状态、发生条件和双型号冲突。

## 12. 跨模态查询计划

最多五条查询，原始查询保留率=1.0；只使用用户/媒体现有信号，低置信度信号标记 hypothesis。

## 13. 跨模态检索

- 状态：`PARTIAL_METRICS_BENCHMARK_LABELS_INSUFFICIENT`
- Candidate Recall@50 / Recall@5 / MRR / nDCG@10：None / None / None / None
- Citation validity / coverage：1.0 / 1.0
- scope leakage：0
- dedicated rerank used：false；Embedding/DashVector/Qwen3/cloud LLM calls：0。

浏览器 no-answer 回归发现并修复了显式不支持型号仍返回通用手册 Citation 的问题；当前未知产品族在检索前返回 `INSUFFICIENT_EVIDENCE`，候选、Citation 和外部调用均为 0。

上述排序指标因 Benchmark 缺少足够的预期 chunk 标签不可计算，不以空值冒充通过。

## 14. Evidence Fusion

证据严格分为 CONFIRMED、OBSERVED、INFERRED、KNOWLEDGE_SUPPORTED；视觉推断不会升级为 CONFIRMED，同来源投票有上限且 Evidence Identity 去重。

## 15. Diagnosis

诊断门：`PASS`；hypotheses=1；unsupported diagnoses=0。无有效官方 Citation 时返回 `INSUFFICIENT_EVIDENCE`。

## 16. Safety Guard

unsafe instructions=0；高风险证据会阻止缺少安全状态和官方依据的危险操作，安全警告永不为空。

## 17. SOP 草稿

边界状态：`PASS`；Task 25C SOP drafts=2，只创建 `sop_draft` Agent Artifact，requires_human_approval=true，automatic SOP approvals=0。

## 18. Task 草稿

Task 25C task drafts=1；只创建 `task_draft` Agent Artifact，要求 SOP 已批准或由用户确认，automatic formal tasks=0。

## 19. 审计和 RBAC

viewer 只读；engineer/expert/admin 可按角色操作；真实 Provider 仅 expert/admin 且双开关启用。当前多模态审计事件=357，已审计案例=27/27，audit coverage=1.0。RBAC 回归：`PASS 40 checks`。

## 20. Benchmark

- dataset：`task25c_multimodal_engineering_benchmark_v1`
- 状态：`MULTIMODAL_BENCHMARK_INSUFFICIENT`
- cases / unique media：30 / 30
- shortages：`{"nameplate_model_ocr": {"actual": 8, "required": 15}, "alarm_code_screen": {"actual": 8, "required": 15}, "indicator_state": {"actual": 0, "required": 10}, "platform_alarm_screen": {"actual": 0, "required": 10}, "low_quality_image": {"actual": 0, "required": 8}, "clarification_required": {"actual": 8, "required": 10}, "no_answer": {"actual": 5, "required": 10}, "high_risk_safety": {"actual": 7, "required": 8}}`
- engineering_verified=true；expert_verified_count=0。

现有工程受控媒体仅支持 30 个可追溯案例，无法满足 80 例与所有类别覆盖，因此最终不得标记 FULL PASS。

## 21. 质量指标

可执行安全/引用/边界检查：`{"media_security": true, "original_query_retained": true, "citation_validity": true, "citation_coverage": true, "scope_leakage_zero": true, "unsupported_diagnosis_zero": true, "unsafe_instruction_zero": true, "sop_task_boundary": true, "integrity": true, "dedicated_rerank_deferred": true}`；不可测指标：`["candidate_recall_at_50", "recall_at_5", "mrr", "ndcg_at_10"]`。

## 22. 性能

- preprocessing：本地定向测试通过；目标 p95≤1000ms。
- retrieval p95：3276.686 ms。
- OCR/vision/total async p95：双门禁已启用并各执行一次，但 Provider 在网络前因禁用/缺配置安全降级；单次 fallback 延迟不冒充 p95。

## 23. 真实 Provider Probe

OCR=`SAFE_FALLBACK`（2210.739 ms），visual=`SAFE_FALLBACK`（2264.634 ms）。CLI 与 `TASK25C_ALLOW_REAL_API=true` 双门禁均已满足，但 OCR Provider disabled、视觉 Provider not configured，均在网络前安全降级，external_api_called=false；未输出 Key、Authorization、完整图片、Prompt 或完整 Provider 响应。

## 24. 完整回归

`{
  "compileall": "PASS",
  "alembic": "PASS heads/current 20260712_0014; downgrade/upgrade verified",
  "pytest": "PASS 326 passed, 3 skipped",
  "security": "PASS blocking=0",
  "rbac": "PASS 40 checks",
  "agents": "PASS 7 flows",
  "conversion": "PASS artifact and concurrency",
  "npm_install": "PASS 113 packages",
  "npm_audit": "PASS 0 vulnerabilities",
  "frontend": "PASS vite build",
  "vue_tsc": "PASS",
  "static_install": "PASS 61 files",
  "browser": "PASS 43 checks",
  "final_smoke": "PASS 23/23 failed=0",
  "real_ocr_probe": "SAFE_FALLBACK provider disabled before network",
  "real_visual_probe": "SAFE_FALLBACK provider not configured before network",
  "cross_modal_retrieval": "PARTIAL_METRICS_BENCHMARK_LABELS_INSUFFICIENT",
  "task25c_regression": "PASS",
  "quality_gate": "MULTIMODAL_BENCHMARK_INSUFFICIENT"
}`

## 25. 前端和浏览器

新增 `/multimodal-maintenance`，覆盖 24 个页面区域。Frontend=PASS vite build；vue-tsc=PASS；Playwright=PASSED，console/page/network failures=0/0/0。

## 26. Final Smoke

`PASS 23/23 failed=0`。

## 27. RAG 专用重排仍待恢复

R6 保持 `DEFERRED_QWEN3_RERANK_CONFIG`；待配置 Workspace 专属 Base URL 后再独立恢复验证。冻结后授权刷新导致 5 个 R6 报告/运行工件 hash 变化，但 Qwen3 调用、Embedding 和向量写入仍为 0，且语义边界复核通过；详见 regression.integrity。

## 28. expert_verified=false

知识 expert_verified 基线=0，当前=0；未写人工专家审核。

## 29. 正式全量重建未执行

`TASK25B_ALLOW_FULL_REINDEX=false`；没有重新生成 Embedding、upsert 向量、修改默认 Partition 或正式全量重建。

## 30. LoongArch 未实机

仍未在 LoongArch + 银河麒麟物理环境验收；当前实现未引入 CUDA、GPU、本地大模型、FAISS、pgvector、Neo4j 或 Docker。

## 31. 未打包

未生成 Task 25C ZIP 或发布包。

## 32. 未提交 Git

未执行 git add/commit/reset/clean/restore。

## 最终结论

`MULTIMODAL_BENCHMARK_INSUFFICIENT`

功能链路已经实现并完成可执行安全边界验证；当前主要阻断是授权且有可靠标签的多模态 Benchmark 只有 30 例，真实 OCR/视觉 Provider 在配置预检处安全降级，且跨模态排序指标缺少足够 ground truth，故不声称工程质量 FULL PASS。
