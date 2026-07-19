from __future__ import annotations

import json
from pathlib import Path

from task25c_common import OUT, ROOT, now_iso, read_json, write_json


def optional(name: str) -> dict:
    path = OUT / name
    return read_json(path) if path.is_file() else {"status": "NOT_EXECUTED"}


def value(payload: dict, *path, default="NOT_AVAILABLE"):
    current = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def main() -> int:
    baseline = read_json("baseline_snapshot.json")
    r6 = read_json("r6_deferred_status.json")
    benchmark = optional("multimodal_benchmark_v1.json")
    media = optional("media_security.json")
    ocr = optional("ocr_probe.json")
    visual = optional("visual_probe.json")
    retrieval = optional("cross_modal_retrieval.json")
    diagnosis = optional("diagnosis_safety.json")
    boundary = optional("sop_task_boundary.json")
    regression = optional("regression.json")
    browser = optional("browser_review.json")
    quality = optional("multimodal_quality_gate.json")
    acceptance = optional("acceptance_results.json")
    counts = regression.get("database_counts") or {}
    integrity = regression.get("integrity") or {}
    draft_counts = boundary.get("artifact_counts") or {}
    metrics = retrieval.get("metrics") or {}
    commands = acceptance.get("results") or {}
    result = quality.get("result") or "MULTIMODAL_ENGINEERING_QUALITY_GATE_FAILED"
    report = f"""# Task 25C 多模态跨模态诊断统一报告

生成时间：{now_iso()}

## 1. 当前系统基线

- 中文正式工程知识文档：{baseline['database_counts']['official_engineering_documents']}
- 中文 active chunks：{baseline['database_counts']['official_active_chunks']}
- Semantic Unit V2：{baseline['database_counts']['semantic_unit_v2']}
- 基线向量 Partition：`{json.dumps(baseline['partition_counts'], ensure_ascii=False)}`
- 基线 Alembic：`{baseline['alembic_current']}`；本任务目标 head 为 `20260712_0014`。

## 2. R6 专用重排延后状态

`{r6['status']}`。Task 25C 检索链路没有调用 Qwen3 rerank、R6 Canary 或 Formal，使用确定性降级链路，不声称 RAG 专用重排正式质量通过。Task 25C 基线之后曾按用户单独的 R6 指令刷新 R6 Probe/浏览器/Smoke 工件，但配置门禁在网络前停止，Qwen3 真实调用仍为 0；原冻结 hash 漂移保留在 regression 证据中，语义边界复核={integrity.get('protected_r6_semantics_preserved_after_authorized_refresh')}。

## 3. 多模态案例模型

已落地 `MultimodalMaintenanceCase`、Evidence、Conflict、Diagnostic Hypothesis 四张表及状态机。当前数据库：cases={counts.get('cases', 0)}、media links={counts.get('media_links', 0)}、evidence={counts.get('evidence_items', 0)}、regions={counts.get('regions', 0)}、conflicts={counts.get('conflicts', 0)}、hypotheses={counts.get('hypotheses', 0)}。

## 4. 媒体安全

状态：`{media.get('status')}`。覆盖 MIME/扩展名/文件头校验、像素与解压炸弹限制、随机文件名、路径边界、SHA-256、去重、EXIF 清理和安全重编码。

## 5. 图片预处理

预处理证据：`{json.dumps(media.get('preprocessing', {}), ensure_ascii=False)}`。原图不覆盖，派生版本保留 hash 和变换参数，无 GPU/CUDA 依赖。

## 6. OCR 证据

确定性 OCR 区域归一、坐标、block hash、型号/告警/参数/通信状态提取已完成。真实 Probe：`{ocr.get('status')}`；原因：`{ocr.get('reason')}`；外部调用={ocr.get('external_api_called', False)}。

## 7. 视觉证据

视觉结构化输出只允许可观察候选，始终保持 INFERRED/LOW_CONFIDENCE，禁止直接诊断和维修步骤。真实 Probe：`{visual.get('status')}`；原因：`{visual.get('reason')}`；外部调用={visual.get('external_api_called', False)}。

## 8. 区域级证据

Evidence 保存 `region_id`、bounding box、source image、locator、attributes 和 confidence；前端支持区域框、证据点击、确认和拒绝。当前持久化 region 数={counts.get('regions', 0)}；因授权媒体不足且真实 OCR/视觉 Provider 在配置预检处安全降级，本轮不能用 0 个真实区域声称区域识别质量达标。

## 9. 实体解析

解析优先级为用户确认、绑定设备、高置信 OCR、视觉推断和案例提示；无法确定时不默认 `pv_inverter`，支持 SUN2000/LUNA2000/SmartLogger/SG。

## 10. 冲突处理

型号、告警、设备绑定、指示灯和跨 Provider 差异以独立 Conflict 记录保存，高风险冲突不得由模型自动消除。

## 11. 主动追问

追问来自固定安全模板，覆盖模糊图片、完整型号、告警码、完整屏幕、指示灯状态、发生条件和双型号冲突。

## 12. 跨模态查询计划

最多五条查询，原始查询保留率={metrics.get('original_query_retained_ratio')}；只使用用户/媒体现有信号，低置信度信号标记 hypothesis。

## 13. 跨模态检索

- 状态：`{retrieval.get('status')}`
- Candidate Recall@50 / Recall@5 / MRR / nDCG@10：{metrics.get('candidate_recall_at_50')} / {metrics.get('recall_at_5')} / {metrics.get('mrr')} / {metrics.get('ndcg_at_10')}
- Citation validity / coverage：{metrics.get('citation_validity')} / {metrics.get('citation_coverage')}
- scope leakage：{metrics.get('scope_leakage')}
- dedicated rerank used：false；Embedding/DashVector/Qwen3/cloud LLM calls：0。

浏览器 no-answer 回归发现并修复了显式不支持型号仍返回通用手册 Citation 的问题；当前未知产品族在检索前返回 `INSUFFICIENT_EVIDENCE`，候选、Citation 和外部调用均为 0。

上述排序指标因 Benchmark 缺少足够的预期 chunk 标签不可计算，不以空值冒充通过。

## 14. Evidence Fusion

证据严格分为 CONFIRMED、OBSERVED、INFERRED、KNOWLEDGE_SUPPORTED；视觉推断不会升级为 CONFIRMED，同来源投票有上限且 Evidence Identity 去重。

## 15. Diagnosis

诊断门：`{diagnosis.get('status')}`；hypotheses={value(diagnosis, 'metrics', 'hypotheses', default=0)}；unsupported diagnoses={value(diagnosis, 'metrics', 'unsupported_diagnoses', default='NOT_AVAILABLE')}。无有效官方 Citation 时返回 `INSUFFICIENT_EVIDENCE`。

## 16. Safety Guard

unsafe instructions={value(diagnosis, 'metrics', 'unsafe_instructions', default='NOT_AVAILABLE')}；高风险证据会阻止缺少安全状态和官方依据的危险操作，安全警告永不为空。

## 17. SOP 草稿

边界状态：`{boundary.get('status')}`；Task 25C SOP drafts={draft_counts.get('sop_drafts', 0)}，只创建 `sop_draft` Agent Artifact，requires_human_approval=true，automatic SOP approvals={boundary.get('automatic_sop_approvals')}。

## 18. Task 草稿

Task 25C task drafts={draft_counts.get('task_drafts', 0)}；只创建 `task_draft` Agent Artifact，要求 SOP 已批准或由用户确认，automatic formal tasks={boundary.get('automatic_formal_tasks')}。

## 19. 审计和 RBAC

viewer 只读；engineer/expert/admin 可按角色操作；真实 Provider 仅 expert/admin 且双开关启用。当前多模态审计事件={counts.get('audits', 0)}，已审计案例={counts.get('audited_cases', 0)}/{counts.get('cases', 0)}，audit coverage={counts.get('audit_coverage', 'NOT_AVAILABLE')}。RBAC 回归：`{commands.get('rbac', 'NOT_EXECUTED')}`。

## 20. Benchmark

- dataset：`{benchmark.get('dataset_version')}`
- 状态：`{benchmark.get('status')}`
- cases / unique media：{benchmark.get('case_count')} / {benchmark.get('unique_media_count')}
- shortages：`{json.dumps(benchmark.get('shortages', {}), ensure_ascii=False)}`
- engineering_verified=true；expert_verified_count={benchmark.get('expert_verified_count', 0)}。

现有工程受控媒体仅支持 30 个可追溯案例，无法满足 80 例与所有类别覆盖，因此最终不得标记 FULL PASS。

## 21. 质量指标

可执行安全/引用/边界检查：`{json.dumps(quality.get('checks', {}), ensure_ascii=False)}`；不可测指标：`{json.dumps(quality.get('unmeasurable_metrics', []), ensure_ascii=False)}`。

## 22. 性能

- preprocessing：本地定向测试通过；目标 p95≤1000ms。
- retrieval p95：{metrics.get('retrieval_p95_ms')} ms。
- OCR/vision/total async p95：双门禁已启用并各执行一次，但 Provider 在网络前因禁用/缺配置安全降级；单次 fallback 延迟不冒充 p95。

## 23. 真实 Provider Probe

OCR=`{ocr.get('status')}`（{ocr.get('latency_ms')} ms），visual=`{visual.get('status')}`（{visual.get('latency_ms')} ms）。CLI 与 `TASK25C_ALLOW_REAL_API=true` 双门禁均已满足，但 OCR Provider disabled、视觉 Provider not configured，均在网络前安全降级，external_api_called=false；未输出 Key、Authorization、完整图片、Prompt 或完整 Provider 响应。

## 24. 完整回归

`{json.dumps(commands, ensure_ascii=False, indent=2)}`

## 25. 前端和浏览器

新增 `/multimodal-maintenance`，覆盖 24 个页面区域。Frontend={commands.get('frontend', 'NOT_EXECUTED')}；vue-tsc={commands.get('vue_tsc', 'NOT_EXECUTED')}；Playwright={browser.get('status', 'NOT_EXECUTED')}，console/page/network failures={len(browser.get('console_errors', []))}/{len(browser.get('page_errors', []))}/{len(browser.get('unexpected_network_failures', []))}。

## 26. Final Smoke

`{commands.get('final_smoke', 'NOT_EXECUTED')}`。

## 27. RAG 专用重排仍待恢复

R6 保持 `DEFERRED_QWEN3_RERANK_CONFIG`；待配置 Workspace 专属 Base URL 后再独立恢复验证。冻结后授权刷新导致 5 个 R6 报告/运行工件 hash 变化，但 Qwen3 调用、Embedding 和向量写入仍为 0，且语义边界复核通过；详见 regression.integrity。

## 28. expert_verified=false

知识 expert_verified 基线={baseline['database_counts']['knowledge_expert_verified']}，当前={counts.get('knowledge_expert_verified')}；未写人工专家审核。

## 29. 正式全量重建未执行

`TASK25B_ALLOW_FULL_REINDEX=false`；没有重新生成 Embedding、upsert 向量、修改默认 Partition 或正式全量重建。

## 30. LoongArch 未实机

仍未在 LoongArch + 银河麒麟物理环境验收；当前实现未引入 CUDA、GPU、本地大模型、FAISS、pgvector、Neo4j 或 Docker。

## 31. 未打包

未生成 Task 25C ZIP 或发布包。

## 32. 未提交 Git

未执行 git add/commit/reset/clean/restore。

## 最终结论

`{result}`

功能链路已经实现并完成可执行安全边界验证；当前主要阻断是授权且有可靠标签的多模态 Benchmark 只有 30 例，真实 OCR/视觉 Provider 在配置预检处安全降级，且跨模态排序指标缺少足够 ground truth，故不声称工程质量 FULL PASS。
"""
    path = ROOT / "docs" / "25C_multimodal_cross_modal_diagnosis_report.md"
    path.write_text(report, encoding="utf-8")
    write_json("report_generation.json", {"generated_at": now_iso(), "status": "GENERATED", "result": result, "report": "docs/25C_multimodal_cross_modal_diagnosis_report.md"})
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
