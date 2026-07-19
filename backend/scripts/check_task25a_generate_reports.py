from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25a"
DOCS = ROOT / "docs"


MATURITY_LABELS = {
    "verified": "A. verified",
    "implemented_but_not_fully_verified": "B. implemented_but_not_fully_verified",
    "partial": "C. partial",
    "placeholder_or_mock": "D. placeholder_or_mock",
    "missing": "E. missing",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(name: str) -> dict[str, Any]:
    return json.loads((RUNTIME / name).read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evidence_catalog() -> dict[str, dict[str, Any]]:
    return {
        "ARCH": {
            "source_files": [
                "backend/app/main.py",
                "frontend/src/router/index.ts",
                "frontend/vite.config.ts",
                "docs/08_deployment_and_loongarch_kylin_spec.md",
                "scripts/check_loongarch_kylin.sh",
            ],
            "api_evidence": "FastAPI 统一 /api 路由与静态 SPA fallback；/api/health 可访问。",
            "database_evidence": "PostgreSQL 42 张表，Alembic current/head 均为 20260601_0008。",
            "frontend_evidence": "Vue Router 使用 history 模式；32 个路由条目；生产静态构建可由后端/Nginx 托管。",
            "test_evidence": "final_smoke_test.ps1 23/23；LoongArch/Kylin 仅有静态检查脚本。",
            "runtime_evidence": "Windows 本机 8010/55432 验证通过；未在 LoongArch/Kylin 实机运行。",
        },
        "MODEL": {
            "source_files": [
                "backend/app/services/model_gateway_service.py",
                "backend/app/services/model_adapters/cloud_openai_adapter.py",
                "backend/app/services/model_adapters/local_llama_cpp_adapter.py",
                "docs/24C_real_external_api_acceptance_report.md",
            ],
            "api_evidence": "/api/model-gateway/status、test、chat 与 provider gateway 路由存在。",
            "database_evidence": "model_call_logs 当前有 264 行；external_api_call_logs 有 301 行。",
            "frontend_evidence": "模型服务页展示 provider 状态、fallback 与调用边界。",
            "test_evidence": "历史 Task 24C 报告记录 Cloud LLM real-call 通过；本轮按约束不调用真实外部 API。",
            "runtime_evidence": "本轮后端强制关闭 Cloud/MIMO/OCR/DashVector/Embedding real call；local llama.cpp 未启动。",
        },
        "UI": {
            "source_files": [
                "frontend/src/router/index.ts",
                "frontend/src/router/menus.ts",
                "frontend/src/layout/index.vue",
                "frontend/src/views",
            ],
            "api_evidence": "Axios baseURL=/api，鉴权 token 由统一拦截器注入。",
            "database_evidence": "页面数据经后端 API 读取 PostgreSQL，无最终业务 mock store。",
            "frontend_evidence": "PC Web 覆盖 dashboard、知识库、检索、诊断、SOP、工单、追溯、图谱、多模态和系统页。",
            "test_evidence": "npm audit 0 漏洞；vue-tsc、Vite build 与静态安装通过。",
            "runtime_evidence": "final smoke 验证 /、/dashboard 与静态资源入口 HTTP 200；本轮未做人工视觉走查。",
        },
        "MM": {
            "source_files": [
                "backend/app/api/routes/media.py",
                "backend/app/api/routes/multimodal_evidence.py",
                "backend/app/services/multimodal_evidence_service.py",
                "backend/app/services/multimodal_result_normalizer.py",
                "backend/app/models/multimodal_evidence.py",
                "frontend/src/views/multimodal/index.vue",
            ],
            "api_evidence": "媒体上传、OCR job、AI analysis、review 与 evidence link API 已注册。",
            "database_evidence": "uploaded_media=139、media_ocr_results=43、media_ai_analyses=48、media_evidence_links=236。",
            "frontend_evidence": "多模态页区分 blocked/dry-run/mock/real、confidence 与人工复核状态。",
            "test_evidence": "check_multimodal_evidence_flow 与 agent flow 本轮通过；主要为 blocked/dry-run/mock 链路。",
            "runtime_evidence": "历史 Task 24C 有 MIMO/OCR real-call 记录；本轮禁止复调且无识别准确率数据集。",
        },
        "RAG": {
            "source_files": [
                "backend/app/services/knowledge_service.py",
                "backend/app/services/document_parser.py",
                "backend/app/services/text_splitter.py",
                "backend/app/services/retrieval_service.py",
                "backend/app/services/hybrid_retrieval_service.py",
                "backend/app/services/vector_index_service.py",
                "backend/app/repositories/retrieval_repository.py",
                "frontend/src/views/knowledge/Search.vue",
                "frontend/src/views/assistant/Chat.vue",
            ],
            "api_evidence": "文档 upload/list/chunks/reparse、/api/retrieval/query、/api/vector-search 路由存在。",
            "database_evidence": "knowledge_documents=111、knowledge_chunks=116、qa_records=265；向量索引 30 行全部 fake_in_memory + deterministic_test。",
            "frontend_evidence": "检索页展示 references、retrieval diagnostics、fallback/vector backend 等边界。",
            "test_evidence": "上传安全、DashVector hybrid 离线 flow 与性能 keyword retrieval 本轮通过。",
            "runtime_evidence": "关键词检索返回真实 5 个 references；真实 DashVector/Embedding 未验收。",
        },
        "DIAG": {
            "source_files": [
                "backend/app/api/routes/diagnosis.py",
                "backend/app/services/diagnosis_service.py",
                "backend/app/services/diagnosis_rule_engine.py",
                "backend/app/models/record.py",
                "frontend/src/views/diagnosis/index.vue",
            ],
            "api_evidence": "/api/diagnosis/analyze 与 records 路由写入并查询诊断记录。",
            "database_evidence": "diagnosis_records 当前 92 行；包含 references、history、media、KG 与 safety 字段。",
            "frontend_evidence": "诊断页展示原因、步骤、安全提示、建议、引用、媒体和 KG 上下文。",
            "test_evidence": "performance diagnosis、RBAC 与 diagnosis/SOP/task agent flow 本轮通过。",
            "runtime_evidence": "规则诊断本轮成功写入；模型增强关闭，不能替代工程师确认。",
        },
        "SOP": {
            "source_files": [
                "backend/app/api/routes/sop.py",
                "backend/app/services/sop_service.py",
                "backend/app/services/sop_rule_engine.py",
                "backend/app/services/sop_execution_service.py",
                "backend/app/models/sop.py",
                "frontend/src/views/sop/index.vue",
            ],
            "api_evidence": "SOP template/generate/execution 的列表、创建、更新、归档 API 已注册。",
            "database_evidence": "sop_templates=44、sop_execution_records=11；模板含 steps/safety/tools/materials/version/status。",
            "frontend_evidence": "SOP 页展示步骤、工具、材料、安全要求与执行状态。",
            "test_evidence": "diagnosis_sop_task_agent_flow 与 artifact conversion flow 本轮通过。",
            "runtime_evidence": "规则型 SOP 和人工审批转换可复现；显式 step prerequisite/stop condition 字段不足。",
        },
        "KNOW": {
            "source_files": [
                "backend/app/api/routes/knowledge_contributions.py",
                "backend/app/api/routes/review.py",
                "backend/app/api/routes/knowledge_graph.py",
                "backend/app/services/knowledge_contribution_service.py",
                "backend/app/services/kg_extraction_service.py",
                "backend/app/services/kg_candidate_service.py",
                "backend/app/services/knowledge_graph_service.py",
                "frontend/src/views/knowledge/Contributions.vue",
                "frontend/src/views/knowledgeGraph/index.vue",
            ],
            "api_evidence": "贡献 submit/approve/convert/archive、KG extract/candidate approve/reject/merge API 已注册。",
            "database_evidence": "knowledge_contributions=36、kg_nodes=34、kg_edges=34、kg_candidates=357、evidence_links=76。",
            "frontend_evidence": "贡献审核与知识图谱页面可展示候选、证据、节点、关系和上下文。",
            "test_evidence": "knowledge curator、artifact conversion、KG business flow 的现有脚本提供集成证据。",
            "runtime_evidence": "本轮 curator/转换通过；341 个 KG 候选仍 pending，质量治理与去重压力较高。",
        },
        "FEEDBACK": {
            "source_files": [
                "backend/app/api/routes/corrections.py",
                "backend/app/services/correction_service.py",
                "backend/app/models/review.py",
                "frontend/src/views/review/Corrections.vue",
            ],
            "api_evidence": "/api/corrections 支持创建、列表、详情与 resolve。",
            "database_evidence": "model_output_corrections=14，其中 accepted=8；converted_contribution_id 全部为空。",
            "frontend_evidence": "人工修正页支持提交、审核、来源 trace 展示。",
            "test_evidence": "RBAC 覆盖部分修正/审核边界；未发现 accepted correction 回流检索或提示词的专项测试。",
            "runtime_evidence": "修正记录可追踪，但 accepted 结果未形成检索/规则/提示词回用闭环。",
        },
        "TASK": {
            "source_files": [
                "backend/app/api/routes/maintenance_tasks.py",
                "backend/app/services/maintenance_task_service.py",
                "backend/app/services/task_workflow_service.py",
                "backend/app/models/maintenance.py",
                "backend/app/models/device_history.py",
                "frontend/src/views/workorder",
            ],
            "api_evidence": "工单 create/assign/start/complete/cancel/list/detail API 已注册并有角色限制。",
            "database_evidence": "maintenance_tasks=46、device_maintenance_records=40；任务关联 SOP、trace、assignee 与结果。",
            "frontend_evidence": "工单创建、列表、详情、状态按钮与来源追踪页面存在。",
            "test_evidence": "RBAC、diagnosis/SOP/task agent flow、artifact conversion 和 final smoke 本轮通过。",
            "runtime_evidence": "任务草稿不会自动成为正式任务；人工批准与显式转换边界可复现。",
        },
        "SEC": {
            "source_files": [
                "backend/app/core/security.py",
                "backend/app/core/security_config.py",
                "backend/app/core/security_middleware.py",
                "backend/app/core/dependencies.py",
                "backend/scripts/check_secret_leak_scan.py",
                "backend/scripts/check_rbac_security_matrix.py",
            ],
            "api_evidence": "JWT、require_roles/require_admin、中间件限流与请求体大小限制已接入。",
            "database_evidence": "users=434；多类 event/call/review/conversion 表可审计，但 operation_logs=0。",
            "frontend_evidence": "路由和菜单按 admin/expert/engineer/viewer 控制；401/403 统一处理。",
            "test_evidence": "安全配置、日志脱敏、上传安全、40 项 RBAC 与 secret scan 本轮通过/通过附注。",
            "runtime_evidence": "生产 guard 能拒绝弱配置；当前 development 的 SECRET_KEY/admin password 仍未达到生产要求。",
        },
        "NFR": {
            "source_files": [
                "frontend/src/style.css",
                "frontend/src/layout/index.vue",
                "backend/app/core/security_middleware.py",
                "backend/app/api/routes/system.py",
                "scripts/final_smoke_test.ps1",
                "docs",
            ],
            "api_evidence": "system status/statistics、统一错误响应、分页接口和日志/trace 字段部分存在。",
            "database_evidence": "42 表可持久化追踪；日志表无保留/分区策略，operation_logs 未形成通用审计覆盖。",
            "frontend_evidence": "PC Web 构建通过，含 loading/error/empty 组件；复杂页面仍暴露较多技术术语。",
            "test_evidence": "compile、DB current、专项 flow、前端 build、93 请求基线与 23/23 smoke 通过；无标准 pytest/长期稳定性测试。",
            "runtime_evidence": "Windows 本地可演示；记录中心并发 p95 1763.863 ms，无 HA/备份恢复实测。",
        },
    }


def requirement_rows() -> list[tuple[str, str, str, str, str, str]]:
    # id, requirement, maturity, gap, severity, recommended action
    return [
        ("R-ARCH-01", "B/S 架构", "verified", "无功能缺口；仍需目标机反向代理部署。", "P2", "保留 FastAPI + Vue B/S 架构。"),
        ("R-ARCH-02", "LoongArch 架构兼容", "partial", "只有静态审计；未完成 LoongArch 安装、启动和闭环。", "P0", "Task 25G 在真实龙芯服务器执行全套部署验收。"),
        ("R-ARCH-03", "银河麒麟 V10/V11 兼容", "partial", "只有 Linux/麒麟文档和脚本；无 V10/V11 实机证据。", "P0", "Task 25G 分别记录 V10/V11 依赖、权限、systemd/Nginx 验收。"),
        ("R-MODEL-01", "云端大模型", "implemented_but_not_fully_verified", "历史 real-call 通过，但本轮禁调且在线可用性会漂移。", "P1", "保留网关；比赛前用轮换密钥做一次受控复验。"),
        ("R-MODEL-02", "本地大模型预留或能力", "implemented_but_not_fully_verified", "有 llama.cpp 适配器但无模型、二进制、性能或 LoongArch 验收。", "P1", "Task 25G 在目标机验证可选 GGUF 服务，失败时明确云模型主路线。"),
        ("R-UI-01", "PC Web 可视化界面", "verified", "本轮无人工视觉/无障碍走查。", "P2", "Task 25F 补浏览器场景、截图基线和可访问性检查。"),

        ("R-MM-01", "文本输入", "verified", "无主要缺口。", "P2", "保留统一文本输入和长度校验。"),
        ("R-MM-02", "图片输入", "verified", "上传闭环可用；大图/损坏图真实 provider 错误仍需复验。", "P1", "Task 25B 增加真实图片集与错误场景。"),
        ("R-MM-03", "设备型号输入", "verified", "型号主要是结构化字段，自动识别准确率未验证。", "P1", "Task 25B 区分人工输入与模型识别结果。"),
        ("R-MM-04", "OCR", "implemented_but_not_fully_verified", "有历史真实调用和持久化，但无当前复验与准确率基准。", "P1", "Task 25B 建立铭牌/告警码 OCR 标注集并计算字段级指标。"),
        ("R-MM-05", "图像理解", "implemented_but_not_fully_verified", "MIMO 历史 real-call 可用；无故障部位识别基准和可复现数据集。", "P1", "Task 25B 建立真实故障图像集和人工复核金标准。"),
        ("R-MM-06", "多模态证据融合", "implemented_but_not_fully_verified", "能融合 OCR/视觉文本和链接，但真实质量仅有限样本。", "P1", "Task 25B 以 accepted evidence 约束诊断/SOP 并验证来源一致性。"),
        ("R-MM-07", "跨模态匹配", "partial", "当前是图像转文本后做文本检索，不是共享向量空间。", "P0", "Task 25B 实现或明确替代方案，并以跨模态 Recall@K 验收。"),
        ("R-MM-08", "相似故障图片检索", "missing", "无图像 embedding、相似图索引或查询 API。", "P1", "Task 25B 新增图像检索设计、索引生命周期和评估集。"),
        ("R-MM-09", "图片到手册章节关联", "partial", "支持人工 evidence link；没有自动图片到 chunk 排序与解释指标。", "P1", "Task 25B 增加候选章节、分数、理由和人工确认。"),

        ("R-RAG-01", "文档上传", "verified", "无主要缺口。", "P2", "保留安全上传、RBAC 和状态机。"),
        ("R-RAG-02", "PDF/DOCX/TXT/MD 解析", "implemented_but_not_fully_verified", "实现完整但本轮上传测试主要覆盖文本；扫描 PDF 不支持。", "P1", "Task 25B 建立四格式样本和解析保真断言。"),
        ("R-RAG-03", "文档切分", "verified", "表格/标题/图注语义边界仍不充分。", "P1", "Task 25B 引入结构感知切分和重复/空/超长 chunk 质量门。"),
        ("R-RAG-04", "语义向量化", "placeholder_or_mock", "仅 deterministic_test；真实 embedding provider 未闭环。", "P0", "Task 25B 完成真实 embedding 版本、维度、批处理和失败恢复。"),
        ("R-RAG-05", "向量检索", "placeholder_or_mock", "仅 fake_in_memory；真实 DashVector 未在线验收。", "P0", "Task 25B 用轮换凭据完成 DashVector 增量索引与查询闭环。"),
        ("R-RAG-06", "关键词检索", "verified", "ILIKE 多字段召回在大数据量下有扫描风险。", "P1", "Task 25E 基于真实数据量优化全文索引/候选集。"),
        ("R-RAG-07", "混合检索", "placeholder_or_mock", "融合算法存在，但向量侧是 fake/deterministic。", "P0", "Task 25B 用真实两路召回、归一化、rerank 和消融实验验收。"),
        ("R-RAG-08", "权限和审核过滤", "partial", "approved/active/parsed 过滤存在；无细粒度文档可见范围。", "P1", "Task 25B 明确文档 ACL/角色范围并在召回前过滤。"),
        ("R-RAG-09", "引用来源", "verified", "引用-答案逐句一致性尚无自动指标。", "P1", "Task 25B 增加 citation precision/faithfulness 检查。"),
        ("R-RAG-10", "文档版本和状态", "implemented_but_not_fully_verified", "状态/审核/归档存在；版本替换与旧向量失效未真实验证。", "P1", "Task 25B 验证更新、reparse、索引失效和回滚语义。"),
        ("R-RAG-11", "检索精度评估", "missing", "没有真实标注查询集及 Recall@K/MRR/nDCG。", "P0", "Task 25B 建立华为/阳光分层金标准集并纳入门禁。"),
        ("R-RAG-12", "检索延迟评估", "implemented_but_not_fully_verified", "仅 Windows 小样本轻量基线，默认 5/20 方案未完整执行。", "P1", "Task 25E 在目标规模和 LoongArch 复测 p50/p95/p99/QPS。"),

        ("R-DIAG-01", "故障诊断", "verified", "规则诊断可用，但不代表真实故障准确率。", "P1", "Task 25B/25D 用案例集验证原因、步骤和安全一致性。"),
        ("R-DIAG-02", "设备历史结合", "implemented_but_not_fully_verified", "代码支持 history/recurrence，本轮性能 probe 关闭 history。", "P1", "Task 25D 增加同设备复发与无历史对照测试。"),
        ("R-DIAG-03", "告警码结合", "implemented_but_not_fully_verified", "字段和规则存在；厂商完整告警码覆盖率未知。", "P1", "Task 25B 建立厂家告警码基准表和覆盖测试。"),
        ("R-DIAG-04", "多模态证据结合", "implemented_but_not_fully_verified", "可消费 OCR/AI evidence，但真实图像端到端样本不足。", "P1", "Task 25B 验证 accepted evidence 对诊断结果的可解释影响。"),
        ("R-DIAG-05", "人工确认边界", "verified", "需在比赛话术中继续避免确定性诊断声明。", "P0", "保留 pending review、审批、safety note 和防自动执行。"),

        ("R-SOP-01", "步骤化 SOP", "verified", "无主要缺口。", "P2", "保留 step_index/title/instruction/expected_result。"),
        ("R-SOP-02", "设备类型个性化", "implemented_but_not_fully_verified", "支持 pv_inverter/device/model 上下文；跨型号差异测试不足。", "P1", "Task 25D 建立 SUN2000/FusionSolar/SG 差异用例。"),
        ("R-SOP-03", "检修等级个性化", "implemented_but_not_fully_verified", "level_1/2/3 字段存在，等级导致的步骤差异证据不足。", "P1", "Task 25D 明确等级规则并做差异断言。"),
        ("R-SOP-04", "工具和备件", "verified", "字段以 JSONB 列表保存，结构约束有限。", "P2", "Task 25D 收紧工具/材料 schema。"),
        ("R-SOP-05", "前置条件", "partial", "前置条件主要写在自然语言，没有独立可校验字段。", "P1", "Task 25D 增加 step prerequisites 和执行 gate。"),
        ("R-SOP-06", "风险提醒", "verified", "需用真实安全手册审校覆盖率。", "P0", "Task 25D 建立高压/停送电安全规则金标准。"),
        ("R-SOP-07", "合规校验", "implemented_but_not_fully_verified", "有 compliance notes/safety rules，但缺独立合规规则版本和结果记录。", "P1", "Task 25D 增加规则 ID、版本、检查结果和审计证据。"),
        ("R-SOP-08", "禁止事项", "partial", "部分安全文本表达禁止项，无结构化 prohibited_actions。", "P1", "Task 25D 增加禁止事项字段和高风险硬阻断。"),
        ("R-SOP-09", "验收标准", "implemented_but_not_fully_verified", "每步 expected_result 存在，任务整体验收 gate 不完整。", "P1", "Task 25D 增加整体验收项和完成前校验。"),
        ("R-SOP-10", "作业中止条件", "partial", "执行状态可 aborted，但模板无显式 stop_conditions。", "P0", "Task 25D 增加中止条件、触发证据和复工审批。"),
        ("R-SOP-11", "SOP 审核和转换", "verified", "需继续保持不自动转正式对象。", "P0", "保留 expert/admin 显式审批和唯一转换审计。"),
        ("R-SOP-12", "SOP 执行记录", "verified", "step_results 是 JSONB，逐步证据字段仍可增强。", "P1", "Task 25D 关联媒体、异常、签名和时间戳。"),

        ("R-KNOW-01", "检修案例上传", "implemented_but_not_fully_verified", "贡献类型可承载案例，比赛真实案例样本覆盖不足。", "P1", "Task 25F 准备审核案例并走完整转换。"),
        ("R-KNOW-02", "经验总结上传", "implemented_but_not_fully_verified", "流程存在；真实用户体验与重复治理不足。", "P1", "Task 25C/25F 验证经验提交、审查、转换和检索命中。"),
        ("R-KNOW-03", "审核", "verified", "无主要缺口。", "P2", "保留 review records 和角色边界。"),
        ("R-KNOW-04", "知识贡献转换", "verified", "转换后质量评估仍不足。", "P1", "Task 25C 增加转换质量门和回溯。"),
        ("R-KNOW-05", "知识图谱候选", "verified", "待审候选积压 341 条。", "P1", "Task 25C 增加去重、批审与质量排序。"),
        ("R-KNOW-06", "图谱审核", "verified", "manager 可直接手工建正式节点，未强制所有节点走候选。", "P1", "Task 25C 明确手工管理员通道的审计规则。"),
        ("R-KNOW-07", "知识更新", "implemented_but_not_fully_verified", "文档/KG 可更新，但索引版本与失效闭环未真实验证。", "P1", "Task 25C 联动文档、chunk、vector、KG 版本。"),
        ("R-KNOW-08", "失效知识归档", "verified", "缺少自动到期/保留策略。", "P2", "Task 25C 增加有效期和归档原因。"),
        ("R-KNOW-09", "重复知识检测", "partial", "目前偏规则/关键词/唯一约束，不是语义去重。", "P1", "Task 25C 使用真实 embedding 与人工标注阈值。"),
        ("R-KNOW-10", "知识质量评估", "partial", "有审核和 evidence count，但无统一质量分与指标。", "P1", "Task 25C 定义来源、完整性、时效、冲突、重复质量分。"),

        ("R-FEEDBACK-01", "模型输出修正", "verified", "无主要缺口。", "P2", "保留来源 trace、前后输出和审核状态。"),
        ("R-FEEDBACK-02", "人工标注", "implemented_but_not_fully_verified", "修正可作标注载体，但缺专用标注任务/数据集导出。", "P1", "Task 25C 增加标注 schema、审核一致性和导出。"),
        ("R-FEEDBACK-03", "修正记录追踪", "verified", "无主要缺口。", "P2", "保留 source_trace_id 与审核人时间。"),
        ("R-FEEDBACK-04", "修正结果回用于检索", "missing", "accepted correction 未写入知识贡献或检索索引。", "P1", "Task 25C 建立 accepted correction 到贡献/chunk/index 的显式转换。"),
        ("R-FEEDBACK-05", "修正结果回用于规则或提示词", "missing", "未发现规则版本或 prompt 版本更新链路。", "P1", "Task 25C 设计人工审批的规则/prompt 变更流程。"),

        ("R-TASK-01", "检修任务创建", "verified", "无主要缺口。", "P2", "保留持久化和来源 trace。"),
        ("R-TASK-02", "分配", "verified", "无主要缺口。", "P2", "保留 assignable user 与角色限制。"),
        ("R-TASK-03", "开始", "verified", "无主要缺口。", "P2", "保留状态机。"),
        ("R-TASK-04", "完成", "verified", "完成前的结构化验收 gate 可增强。", "P1", "Task 25D 联动 SOP 验收和证据完整性。"),
        ("R-TASK-05", "取消", "verified", "无主要缺口。", "P2", "保留取消原因审计。"),
        ("R-TASK-06", "作业记录", "verified", "记录字段存在；现场逐步证据可增强。", "P1", "Task 25D 关联 SOP step results 和维护履历。"),
        ("R-TASK-07", "证据附件", "implemented_but_not_fully_verified", "media 可关联 task，但完整任务证据浏览器场景未复验。", "P1", "Task 25F 增加上传、预览、权限和追溯浏览器验收。"),
        ("R-TASK-08", "全程追溯", "verified", "跨表追踪性能和保留策略不足。", "P1", "Task 25E 优化 record center 并定义保留策略。"),

        ("R-SEC-01", "JWT", "verified", "logout 不撤销已签发 token。", "P1", "生产需要短 token/刷新或撤销策略。"),
        ("R-SEC-02", "RBAC", "verified", "40 项矩阵通过；需随新路由持续扩展。", "P0", "将 RBAC 矩阵纳入每次回归。"),
        ("R-SEC-03", "文件上传安全", "verified", "真实恶意文件内容扫描不在范围。", "P1", "Task 25E 增加 MIME/病毒扫描策略评估。"),
        ("R-SEC-04", "日志脱敏", "verified", "历史日志仍需轮换和离线审计。", "P1", "Task 25E 增加集中日志与保留策略。"),
        ("R-SEC-05", "API 限流", "implemented_but_not_fully_verified", "进程内限流不适合多实例且本轮未做 429 行为专项。", "P1", "Task 25E 增加分布式/代理层限流和行为测试。"),
        ("R-SEC-06", "请求体限制", "verified", "无主要缺口。", "P2", "保留 JSON/上传两类限制。"),
        ("R-SEC-07", "密钥治理", "partial", "secret scan 无 blocking，但本机有配置密钥且生产 SECRET_KEY/admin password 不合格；历史泄漏密钥需轮换。", "P0", "上线前轮换、使用外部 secret 注入并通过 production guard。"),
        ("R-SEC-08", "审计日志", "implemented_but_not_fully_verified", "业务专项表丰富，但 operation_logs=0、无统一留存/防篡改。", "P1", "Task 25E 统一审计事件、留存、查询和告警。"),

        ("R-NFR-01", "界面美观", "implemented_but_not_fully_verified", "构建通过但本轮无视觉基线与人工评审。", "P2", "Task 25F 做比赛分辨率截图和视觉走查。"),
        ("R-NFR-02", "交互便捷", "implemented_but_not_fully_verified", "loading/error/empty 较完整；复杂技术状态对现场用户偏重。", "P2", "Task 25F 将技术细节折叠为高级信息。"),
        ("R-NFR-03", "文档完整", "implemented_but_not_fully_verified", "文档多，但 README 仍有泛新能源/储能表述与旧端口。", "P2", "Task 25H 冻结前统一范围、端口和能力边界。"),
        ("R-NFR-04", "系统稳定", "implemented_but_not_fully_verified", "专项脚本和 smoke 稳定；无 soak/故障注入/恢复测试。", "P1", "Task 25E 增加长稳、重启、数据库中断和失败恢复。"),
        ("R-NFR-05", "系统易用", "implemented_but_not_fully_verified", "PC Web 完整；未做目标用户可用性测试。", "P2", "Task 25F 用工程师场景计时和错误率验收。"),
        ("R-NFR-06", "可维护性", "partial", "分层良好，但 42 组重复候选、24 个死代码候选、12 处生产 broad except。", "P2", "Task 25H 分批复核候选，不在本任务删除。"),
        ("R-NFR-07", "可观测性", "partial", "有 status/trace/log 表；无指标、告警、分布式 tracing 和容量看板。", "P1", "Task 25E 增加 Prometheus 风格指标或等价轻量方案。"),
        ("R-NFR-08", "备份恢复", "missing", "未发现正式 backup/restore 脚本与恢复演练证据。", "P0", "Task 25E/25G 增加 PostgreSQL 与上传文件一致性备份恢复演练。"),
    ]


def catalog_key(requirement_id: str) -> str:
    if requirement_id.startswith("R-ARCH"):
        return "ARCH"
    if requirement_id.startswith("R-MODEL"):
        return "MODEL"
    if requirement_id.startswith("R-UI"):
        return "UI"
    return requirement_id.split("-")[1]


def build_traceability() -> dict[str, Any]:
    catalog = evidence_catalog()
    entries: list[dict[str, Any]] = []
    for requirement_id, requirement, maturity, gap, severity, action in requirement_rows():
        evidence = catalog[catalog_key(requirement_id)]
        entries.append(
            {
                "requirement_id": requirement_id,
                "requirement": requirement,
                "maturity_level": maturity,
                "source_files": evidence["source_files"],
                "api_evidence": evidence["api_evidence"],
                "database_evidence": evidence["database_evidence"],
                "frontend_evidence": evidence["frontend_evidence"],
                "test_evidence": evidence["test_evidence"],
                "runtime_evidence": evidence["runtime_evidence"],
                "gap": gap,
                "severity": severity,
                "recommended_action": action,
            }
        )
    summary = Counter(item["maturity_level"] for item in entries)
    return {
        "generated_at": utc_now(),
        "audit_policy": "verified requires at least two evidence classes and a passing executable check; mock/fallback is never promoted to real capability",
        "summary": {key: summary.get(key, 0) for key in MATURITY_LABELS},
        "requirements": entries,
    }


def escape_cell(value: Any) -> str:
    if isinstance(value, list):
        value = "<br>".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def traceability_markdown(traceability: dict[str, Any]) -> str:
    summary = traceability["summary"]
    lines = [
        "# Task 25A 赛题需求可追踪矩阵",
        "",
        f"> 生成时间：{traceability['generated_at']}。本矩阵只将具备至少两类证据且执行检查通过的能力标为 verified；mock、fallback、blocked、dry-run 与静态存在不等于真实能力。",
        "",
        "## 1. 汇总",
        "",
        "| maturity_level | count |",
        "|---|---:|",
    ]
    for key in MATURITY_LABELS:
        lines.append(f"| {key} | {summary[key]} |")
    lines.extend(
        [
            "",
            "共 83 项。当前零分级风险集中在 LoongArch/Kylin 未实机验收、真实语义/跨模态检索缺失、生产密钥治理与备份恢复缺口。",
            "",
            "## 2. 逐项追踪",
            "",
            "| requirement_id | requirement | maturity_level | source_files | API evidence | database evidence | frontend evidence | test evidence | runtime evidence | gap | severity | recommended action |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in traceability["requirements"]:
        cells = [
            item["requirement_id"],
            item["requirement"],
            item["maturity_level"],
            item["source_files"],
            item["api_evidence"],
            item["database_evidence"],
            item["frontend_evidence"],
            item["test_evidence"],
            item["runtime_evidence"],
            item["gap"],
            item["severity"],
            item["recommended_action"],
        ]
        lines.append("| " + " | ".join(escape_cell(cell) for cell in cells) + " |")
    lines.extend(
        [
            "",
            "## 3. 解释边界",
            "",
            "- Cloud LLM、MIMO/Vision、OCR API 采用历史 Task 24C real-call 报告与当前数据库持久化作为 B 级证据；本轮按要求未重调外部 API，因此不提升为当前在线 verified。",
            "- DashVector/Embedding 的当前 30 条索引元数据全部来自 fake_in_memory/deterministic_test，只能评为 placeholder_or_mock。",
            "- 图片 OCR/视觉描述再转文本检索只算文本化增强，不算共享图文向量空间或相似图片检索。",
            "- LoongArch/Kylin 只有静态兼容分析，不能写成实机通过。",
        ]
    )
    return "\n".join(lines)


def loongarch_report(dependencies: dict[str, Any]) -> str:
    native = dependencies["python"]["native_or_system_dependency_risks"]
    native_text = "; ".join(f"{item['dependency']}: {item['risk']}" for item in native)
    rows = [
        (1, "Python 版本", "likely_compatible", ">=3.10；需在目标仓库确认可安装版本。"),
        (2, "FastAPI", "likely_compatible", "主要为 Python；受 pydantic-core/Starlette 依赖影响。"),
        (3, "Uvicorn", "requires_build", "uvicorn[standard] 锁定 httptools/uvloop/watchfiles/websockets，可能无 LoongArch wheel。"),
        (4, "Psycopg", "requires_build", "需目标机 libpq/PostgreSQL client library；未使用 psycopg-binary。"),
        (5, "PostgreSQL", "likely_compatible", "正式路线为麒麟 native service；本轮仅 Windows 55432 验证。"),
        (6, "PDF 解析库", "static_compatible", "pypdf 为纯 Python；扫描 PDF 仍需 OCR。"),
        (7, "DOCX 解析库", "requires_build", "python-docx 依赖 lxml，需要 LoongArch libxml2/libxslt 或源码构建。"),
        (8, "Pillow", "unknown", "当前直接依赖未声明；图像链路主要保存/转发，后续引入需重新审计。"),
        (9, "OCR 依赖", "high_risk", "Tesseract 是系统二进制与语言包；OCR API 可绕过本地引擎但依赖网络。"),
        (10, "浏览器测试依赖", "high_risk", "Node browser 脚本存在；目标机无浏览器/驱动验收。"),
        (11, "Node.js", "unknown", "正式运行可仅托管预构建静态文件；目标机源码构建版本未确认。"),
        (12, "npm 包", "high_risk", "Vite 8/Rolldown 锁含平台二进制包，未见 LoongArch binding。"),
        (13, "前端构建结果", "static_compatible", "Windows npm build 与静态安装通过；产物可由 Nginx/后端托管。"),
        (14, "shell/PowerShell", "requires_build", "19 个 PowerShell 与 14 个 shell 文件；Linux 需只使用 .sh 等价路径。"),
        (15, "Windows 路径硬编码", "high_risk", "多份运维/测试脚本含 D:\\Work Space 或本机端口。"),
        (16, "反斜杠路径", "requires_build", "Python 生产代码多用 pathlib，但 Windows check 脚本不可直接搬迁。"),
        (17, "Windows 服务调用", "requires_build", "Get-Service/Start-Process 等仅本机运维；生产需 systemd。"),
        (18, "exe 调用", "requires_build", "PowerShell 脚本调用 .exe；Linux 必须走无后缀命令与 systemd。"),
        (19, "native wheel", "high_risk", native_text or "未识别到风险包，但仍需目标机安装验证。"),
        (20, "x86_64-only wheel", "unknown", "锁文件包含 Windows/x64 npm binding；Python wheel 平台选择未实机解析。"),
        (21, "CUDA/GPU", "static_compatible", "核心依赖未要求 CUDA/GPU；符合 CPU-first 方向。"),
        (22, "Docker", "static_compatible", "未发现 Dockerfile/compose；正式路线非 Docker。"),
        (23, "gcc/g++/Rust", "requires_build", "pydantic-core/watchfiles/greenlet/lxml 可能需要编译器，部分包需要 Rust。"),
        (24, "系统库", "requires_build", "PostgreSQL/libpq、libxml2/libxslt、Tesseract/language pack 需系统包。"),
        (25, "可能无法安装的包", "high_risk", "pydantic-core、uvloop、httptools、watchfiles、lxml 与 Rolldown binding 是重点。"),
        (26, "systemd 启动", "high_risk", "docs 描述了路线，但仓库根未发现 .service 产物。"),
        (27, "Nginx 静态服务", "high_risk", "docs 描述了路线，但仓库根未发现 Nginx .conf 产物。"),
        (28, "文件权限", "unknown", "上传/日志可写校验仅 Windows；麒麟用户、目录、umask 未验证。"),
        (29, "SELinux/安全策略", "unknown", "无麒麟安全策略/端口/目录上下文实测。"),
        (30, "资源占用", "high_risk", "四核 8GB 未测；本地 record center 并发 p95 1763.863 ms。"),
    ]
    lines = [
        "# Task 25A LoongArch / 银河麒麟静态兼容审计",
        "",
        "> 结论：**high_risk**。这是静态审计，不是实机通过。最大风险是原生/Rust 包、Vite/Rolldown 平台二进制、缺少正式 systemd/Nginx 产物以及四核 8GB 未压测。",
        "",
        "## 1. 依赖基线",
        "",
        f"- Python：{dependencies['python']['requires_python']}；锁定包 {dependencies['python']['locked_package_count']} 个。",
        f"- npm lock package entries：{dependencies['frontend']['locked_package_entries']}。",
        f"- PowerShell：{dependencies['platform_coupling']['powershell_script_count']}；shell：{dependencies['platform_coupling']['shell_script_count']}。",
        "- 正式运行建议预构建前端，目标机只运行 Nginx + FastAPI + PostgreSQL；但仍必须在目标机验证 Python native/Rust 依赖。",
        "",
        "## 2. 三十项静态审计",
        "",
        "| # | item | conclusion | evidence / gap |",
        "|---:|---|---|---|",
    ]
    lines.extend(f"| {number} | {item} | {status} | {detail} |" for number, item, status, detail in rows)
    lines.extend(
        [
            "",
            "## 3. 目标机验收门",
            "",
            "1. 在 LoongArch + 银河麒麟 V10/V11 建立干净 Python venv，逐个安装锁定依赖并保存 wheel/build 日志。",
            "2. 安装 native PostgreSQL，执行现有 migration 链到 20260601_0008，并核对 42 张表。",
            "3. 增加并验证 systemd service、Nginx 配置、上传/日志目录权限与安全策略。",
            "4. 运行 compile、专项 flow、前端静态服务、final smoke、性能基线和备份恢复。",
            "5. 任何单项未执行均必须标记 unknown/high_risk，不能表述为实机通过。",
        ]
    )
    return "\n".join(lines)


def test_report(test_inventory: dict[str, Any], performance: dict[str, Any]) -> str:
    coverage = test_inventory["coverage_matrix"]
    dimensions = [
        "unit_test",
        "service_test",
        "api_test",
        "browser_test",
        "performance_test",
        "security_test",
        "real_provider_test",
        "loongarch_test",
    ]
    lines = [
        "# Task 25A 测试覆盖与质量门禁报告",
        "",
        "## 1. 结论",
        "",
        f"- 专项 check/smoke/browser/运维脚本盘点：{test_inventory['summary']['test_or_check_files']} 个。",
        "- 标准 pytest 单元测试体系：**missing**。pyproject 未声明 pytest，仓库无标准 tests/ 单元测试套件。",
        f"- 浏览器脚本：{test_inventory['summary']['browser_test_files']} 个，但本轮未执行浏览器点击验收。",
        f"- 安全脚本：{test_inventory['summary']['security_test_files']} 个；本轮安全配置、secret scan、日志脱敏、上传安全、40 项 RBAC 通过/通过附注。",
        f"- 真实 provider 脚本：{test_inventory['summary']['real_provider_test_files']} 个；本轮按约束未调用外部 API，历史 Task 24C 证据不可替代当前在线可用性。",
        "- LoongArch：只有静态脚本，无实机测试。",
        "",
        "## 2. 本轮质量门",
        "",
        "| gate | result | evidence |",
        "|---|---|---|",
        "| compileall | passed | app 与 scripts 编译通过 |",
        "| Alembic heads/current | passed | 20260601_0008 (head) |",
        "| ruff | missing | pyproject 未配置，不擅自格式化 |",
        "| mypy | missing | pyproject 未配置 |",
        "| security config | passed | development 有 warning；production 弱配置能被拒绝 |",
        "| secret scan | passed_with_notes | 3 个本机 .env configured note，0 blocking；不输出值 |",
        "| log sanitization | passed | 无 raw secret/Authorization/base64/local path |",
        "| upload security | passed | 11 checks |",
        "| RBAC | passed | 40 checks, failed=0 |",
        "| DashVector hybrid flow | passed as mock boundary | fake_in_memory + deterministic_test；非真实向量 |",
        "| external gateway | passed as blocked/dry-run | real_external_calls_enabled=false |",
        "| multimodal evidence | passed as blocked/mock boundary | 本轮未 real-call |",
        "| agent flows | passed | multimodal、diagnosis/SOP/task、curator、conversion、并发防重 |",
        "| npm install/audit | passed | 113 packages，0 vulnerabilities |",
        "| type check/build | passed | vue-tsc --noEmit、vue-tsc -b、Vite build |",
        "| frontend static install | passed | copied 59 files |",
        "| final smoke | passed | 23 total，0 failed；retrieval POST 默认跳过，但性能 probe 已覆盖 |",
        "| browser click | not executed | 现有 8 个脚本未在本轮运行 |",
        "| LoongArch/Kylin | not executed | 无目标机 |",
        "",
        "## 3. 核心模块覆盖矩阵（静态盘点）",
        "",
        "| module | " + " | ".join(dimensions) + " |",
        "|---|" + "|".join("---" for _ in dimensions) + "|",
    ]
    for module, row in coverage.items():
        lines.append("| " + module + " | " + " | ".join(row[dimension] for dimension in dimensions) + " |")
    lines.extend(
        [
            "",
            "## 4. 性能门",
            "",
            f"- 实际运行参数：warmup={performance['scope']['warmup_per_endpoint']}、serial={performance['scope']['serial_iterations_per_endpoint']}、read concurrency={performance['scope']['read_only_concurrency']}。",
            f"- 请求：{performance['overall']['requests']}；error rate={performance['overall']['error_rate']}；p50={performance['overall']['p50_ms']} ms；p95={performance['overall']['p95_ms']} ms；p99={performance['overall']['p99_ms']} ms。",
            "- 为避免应用每分钟 120 次限流把基准污染为 429，本轮未执行脚本默认的 5/20/5 全组合；因此只能算轻量基线。",
            "- 记录中心全量聚合和内存分页是已确认性能风险。",
            "",
            "## 5. 必补门禁",
            "",
            "1. pytest 单元/服务/API 分层套件和覆盖率阈值。",
            "2. 真实检索评估集、OCR/视觉标注集和 citation faithfulness。",
            "3. 浏览器关键路径、重复提交、权限、网络失败和证据展示。",
            "4. 并发/长稳/故障恢复/日志增长/备份恢复。",
            "5. LoongArch/Kylin 实机安装、启动、业务闭环和性能。",
        ]
    )
    return "\n".join(lines)


def roadmap_report() -> str:
    tasks = [
        ("Task 25B", "多模态识别与高精度检索主链路重构", "真实图文识别、跨模态/语义检索、DashVector/Embedding、rerank、评估集", "RAG、多模态、media、vector、retrieval、前端证据展示", "P0", "轮换 provider 密钥；确定 embedding/图像检索方案；准备标注集", "真实 embedding/DashVector 闭环；跨模态/检索指标达门；引用可解释", "可能", "是", "建议后期复测", "高：外部 API、维度一致性、数据集质量", "XL"),
        ("Task 25C", "知识治理、知识图谱与反馈闭环增强", "修正回用、语义去重、KG 版本/冲突/质量、候选积压治理", "correction、contribution、KG、review、index lifecycle", "P1", "Task 25B 提供真实 embedding 与质量指标", "accepted correction 可显式转贡献；KG 质量分、版本、冲突和追溯闭环", "可能", "否（除非真实 embedding 走外部）", "否", "中高：历史数据兼容和候选污染", "L"),
        ("Task 25D", "标准化作业和安全合规闭环增强", "前置/完成/中止条件、禁止项、PPE、合规规则版本、任务验收 gate", "SOP、execution、task、maintenance record、approval", "P0/P1", "收集厂家/现场安全规范并由专家审校", "高风险操作硬阻断；SOP 到任务到记录到知识的证据闭环", "是", "否", "否", "高：安全规则错误会造成现场风险", "L"),
        ("Task 25E", "性能、稳定性、可观测性与压力测试", "优化 record center、索引/查询、限流、日志保留、指标、备份恢复、长稳", "repositories、middleware、logs、system、scripts", "P0/P1", "固定数据规模和性能 SLO；准备可恢复测试库", "四核 8GB 目标；p95/QPS/error rate 达门；备份恢复成功", "可能", "否", "最终需", "中高：压测污染数据或误伤服务", "L"),
        ("Task 25F", "比赛演示场景、前端交互和测试数据完善", "真实场景、技术状态降噪、浏览器点击、截图基线、失败态和证据叙事", "frontend、demo data、browser scripts、docs", "P1/P2", "25B-25E 主链路冻结；准备可公开样例", "关键路径浏览器通过；无 mock 冒充；演示可在限定时间复现", "否", "否", "否", "中：演示数据与真实能力边界混淆", "M"),
        ("Task 25G", "LoongArch / 银河麒麟实机部署验收", "依赖构建、PostgreSQL、systemd、Nginx、权限、安全策略、性能、备份", "deploy、shell、backend/frontend static、database", "P0", "真实 LoongArch + Kylin V10/V11 机器；25B-25F 冻结", "实机完整闭环与重启恢复；保存命令、版本、日志和性能证据", "否（只执行既有 migration）", "可选，除非比赛路线依赖云 provider", "是", "极高：零分硬门、native wheel 与系统库", "XL"),
        ("Task 25H", "无用代码清理、变更分组和交付冻结", "逐项复核 dead/duplicate/deprecated candidates，范围文案、端口、构建产物与 Git 冻结", "全仓、docs、static、legacy、scripts", "P1/P2", "25B-25G 验收完成；人工确认每个候选", "无误删动态注册/migration；分组变更可审计；最终 no-package/交付策略明确", "否", "否", "否", "中：动态路由/注册误删与脏工作树混入", "M"),
    ]
    lines = [
        "# Task 25A 重构决策与路线图",
        "",
        "## 1. 主方案",
        "",
        "**选择 C：关键主链路重构。**",
        "",
        "不建议整体重写。现有 FastAPI/Vue/PostgreSQL 分层、JWT/RBAC、知识文档、任务、记录、KG、Agent 审批/转换和审计表具有保留价值；需要重构的是决定赛题竞争力的真实多模态识别、语义/跨模态检索、SOP 安全 gate、性能和目标机部署主链路。",
        "",
        "## 2. Keep / Enhance / Refactor",
        "",
        "- KEEP：FastAPI + Vue B/S、PostgreSQL/Alembic、统一 /api、JWT/RBAC、上传安全、任务状态机、Agent 人工审批/转换。",
        "- ENHANCE：知识贡献/KG、记录中心、前端证据展示、审计日志、测试体系。",
        "- MAJOR_REFACTOR：真实 Embedding/DashVector/hybrid/rerank/评估、跨模态匹配、SOP 合规与中止条件。",
        "- REMOVE_CANDIDATE：只记录在 JSON 候选清单；Task 25A 不执行清理。",
        "- REPLACE：只在目标机证明依赖不可安装或真实检索方案不达标时替换具体 adapter，不替换主架构。",
        "",
        "## 3. 后续任务",
        "",
    ]
    labels = ["任务", "目标", "涉及模块", "优先级", "前置条件", "验收标准", "是否涉及 migration", "是否涉及真实外部 API", "是否需要 LoongArch", "风险", "工作量"]
    for task in tasks:
        lines.append(f"### {task[0]}：{task[1]}")
        lines.append("")
        for label, value in zip(labels[1:], task[2:]):
            lines.append(f"- {label}：{value}")
        lines.append("")
    lines.extend(
        [
            "## 4. 执行顺序与停止条件",
            "",
            "1. 25B 先补零分/竞争力主链路；真实 embedding/vector 未通过前，不宣称语义或跨模态检索。",
            "2. 25C/25D 在 25B 的索引与证据模型上闭环治理和作业安全。",
            "3. 25E 用固定数据规模验证，不为通过测试关闭安全边界。",
            "4. 25F 只展示已验证能力；mock/dry-run 必须显式标识。",
            "5. 25G 是最终硬门；没有实机日志不得进入“已满足 LoongArch/Kylin”结论。",
            "6. 25H 最后清理候选；每个文件先证据复核，migration 永不作为清理对象。",
        ]
    )
    return "\n".join(lines)


def global_report(
    traceability: dict[str, Any],
    file_inventory: dict[str, Any],
    code_inventory: dict[str, Any],
    performance: dict[str, Any],
    dead: dict[str, Any],
    duplicate: dict[str, Any],
    deprecated: dict[str, Any],
) -> str:
    summary = traceability["summary"]
    categories = file_inventory["summary"]["categories"]
    code_categories = code_inventory["by_category"]
    endpoint = {item["name"]: item for item in performance["endpoints"]}
    lines = [
        "# Task 25A 赛题对标与全量代码审计报告",
        "",
        f"> 审计生成时间：{utc_now()}。扫描 tracked/untracked 文本源码；storage 只统计目录/数量，不读取用户内容；未调用真实外部 API；未打包、未提交 Git、未修改 migration。",
        "",
        "## 1. Executive Summary",
        "",
        "1. 当前整体成熟度：工程底座与传统业务闭环较成熟，但决定赛题竞争力的真实语义/跨模态检索、目标机部署与质量评估未达标。",
        "2. 具备继续增量重构基础：是。分层、数据库、审核/转换、前端和专项脚本可保留。",
        "3. 是否建议整体重写：否。整体重写会丢失已验证持久化和审计能力。",
        "4. 是否建议局部重构：是，但主方案不是零散修补，而是关键主链路重构。",
        "5. 最大赛题风险：LoongArch + 银河麒麟未实机验收，且仓库缺正式 systemd/Nginx 产物。",
        "6. 最大技术风险：真实 embedding/DashVector/共享图文向量缺失，hybrid 仍是 fake/deterministic。",
        "7. 最大性能风险：record center 对多表全量取数、内存排序后分页；并发 p95 1763.863 ms。",
        "8. 最大演示风险：UI 可展示 mock/dry-run/real 状态，但若讲解不严谨会把历史 real-call、当前 blocked 和 mock 混为一谈。",
        "",
        "**最终主方案：C. 关键主链路重构。**",
        "",
        "## 2. Competition Hard Gates",
        "",
        "| gate | judgment | evidence / risk |",
        "|---|---|---|",
        "| B/S | verified | FastAPI + Vue SPA，final smoke 静态入口与 API 通过 |",
        "| LoongArch | partial / P0 | 静态审计 high_risk，无实机 |",
        "| 银河麒麟 | partial / P0 | 无 V10/V11 安装、systemd、Nginx、权限证据 |",
        "| PC Web | verified | 32 路由，build 与静态安装通过 |",
        "| 云端/本地模型 | B | 云模型历史 real-call；本地 llama.cpp 仅预留 |",
        "| 多模态 | B/C | OCR/MIMO 有历史 real-call；跨模态共享向量和相似图片检索缺失 |",
        "| 知识检索 | A + D | 关键词/references verified；向量/hybrid 为 mock boundary |",
        "| 标准化作业 | A/B/C | 结构化步骤/安全/工具可用；显式前置/禁止/中止 gate 不完整 |",
        "| 知识沉淀 | A/B | 贡献、审核、KG、转换存在；修正回用和质量评分不足 |",
        "| 人工修正 | A + E | 修正记录可追踪；accepted 结果不回流检索/规则 |",
        "",
        "## 3. Requirement Traceability Summary",
        "",
        f"- verified：{summary['verified']}",
        f"- implemented_but_not_fully_verified：{summary['implemented_but_not_fully_verified']}",
        f"- partial：{summary['partial']}",
        f"- placeholder_or_mock：{summary['placeholder_or_mock']}",
        f"- missing：{summary['missing']}",
        "",
        "逐项 12 字段证据见 `docs/25A_competition_requirement_traceability_matrix.md` 与 `.runtime/task25a/requirement_traceability.json`。",
        "",
        "## 4. Architecture Audit",
        "",
        "- 生产主线基本遵循 api -> service -> repository -> model；174 个 FastAPI route decorators 均集中注册。",
        "- API 层多数只做参数/权限/服务调用，但 system status 含直接 SQL，部分 route 各自重复 ok/fail helper。",
        "- 事务通常由 service commit/rollback；repository 主要 flush/refresh。Agent artifact conversion 有数据库唯一约束和并发防重。",
        "- 当前 42 张表、8 个 migration，model metadata 与 current 20260601_0008 可启动。",
        "- 生产代码发现 12 处 broad Exception，多数位于 adapter/parser/安全边界；需要逐项确认是否保留足够错误码与可观测性。",
        "- 未发现 Docker 正式路线；没有 deploy/、systemd .service 或 Nginx .conf，是部署硬缺口。",
        "",
        "## 5. Backend Audit",
        "",
        f"- 后端生产代码：{code_categories['backend_production_code']['files']} 文件 / {code_categories['backend_production_code']['lines']} 行。",
        "- 分层、分页、RBAC、PostgreSQL 持久化总体清晰；42 表真实存在。",
        "- RecordCenterRepository._collect_items 对最多 11 种记录分别全量读取，再 Python 排序/分页，数据增长后是明确瓶颈。",
        "- RetrievalRepository 使用多字段 ILIKE 和 JSONB cast，candidate_limit=100 可控但会随文档规模放大扫描成本。",
        "- JSONB 广泛用于 steps/references/context/log/artifact；当前索引以 BTree 为主，需按真实查询再决定 GIN，不能盲加。",
        "- Auth logout 是无状态成功返回，不撤销 JWT；生产需短时 token、刷新/撤销或等价策略。",
        "- Adapter broad exception 会清洗外部错误，但必须避免把 provider 失败变成业务伪成功；现有 diagnostics/fallback 字段值得保留。",
        "",
        "## 6. Frontend Audit",
        "",
        f"- 前端生产代码：{code_categories['frontend_production_code']['files']} 文件 / {code_categories['frontend_production_code']['lines']} 行；32 个路由。",
        "- Axios 统一 baseURL=/api；源码中无 127.0.0.1 硬编码、console.log、debugger、v-html、innerHTML 或显式 any。",
        "- 角色路由与菜单覆盖 admin/expert/engineer/viewer；40 项后端 RBAC 脚本通过。",
        "- mock 相关词 87 处、dry-run 29 处、fallback 17 处，主要用于诚实展示边界；比赛 UI 应把技术细节折叠，避免误解。",
        "- 静态扫描发现 24 个死代码/未引用候选，含 3 个 API 模块和若干图片；动态路由/导入存在，Task 25A 不处理。",
        "- 本轮没有浏览器人工走查，不能仅凭 build 认定视觉、交互、无障碍完全达标。",
        "",
        "## 7. Multimodal Capability Audit",
        "",
        "- 图片上传：verified；上传安全与 RBAC 当前通过。",
        "- OCR：有 provider、job、结果、confidence、regions 与历史 real-call 证据；无准确率集。",
        "- 视觉理解：有告警码、设备信息、视觉发现、可能故障、安全风险、建议和人工复核字段；无部位识别金标准。",
        "- 多模态融合：能把 accepted/manual/real evidence 链接到 QA、诊断、SOP、Agent；本轮 flow 主要是 blocked/mock。",
        "- 图像 embedding：不存在。文本与图像统一向量空间：不存在。相似图片检索：不存在。",
        "- 图片到 chunk：支持人工 evidence link，但没有自动匹配排序/解释指标。",
        "- 最终判断：真实 OCR/视觉为 B，融合为 B，跨模态匹配为 C，相似图检索为 E。",
        "",
        "## 8. Retrieval and RAG Audit",
        "",
        "- 上传 -> 安全 -> 解析 -> 清洗 -> 切分 -> 审核 -> 关键词召回 -> 引用 -> QA 记录闭环可用。",
        "- 召回强制 parsed + active + approved document 和 active chunk，来源真实。",
        "- 切分保存 section_title/page_number，但表格、图注、复杂标题层级保真无专项验收。",
        "- 真实 embedding/DashVector 未闭环；30 条 vector index 全部 fake_in_memory + deterministic_test。",
        "- hybrid merge 有权重、归一化、min score，但在真实向量缺失时只能算 D。",
        "- 未发现独立 reranker 或真实检索评估集；query expansion 是规则词扩展，不是模型 rewrite。",
        "- 关键词基线 4 次串行 p50=" + str(endpoint["keyword_retrieval"]["serial"]["p50_ms"]) + " ms、p95=" + str(endpoint["keyword_retrieval"]["serial"]["p95_ms"]) + " ms。",
        "- 最终判断：可演示可信关键词检索，但未达到高精度语义/跨模态比赛竞争力。",
        "",
        "## 9. Knowledge Base and Knowledge Graph Audit",
        "",
        "- KG 包含 nodes、edges、aliases、evidence、extraction runs、candidates、审批与 node merge。",
        "- 业务 context 已接入 retrieval、diagnosis、SOP，不只是展示。",
        "- 节点 canonical + alias、边唯一检查和 merge 处理部分重复；缺统一版本/有效期/冲突决策记录。",
        "- approved/parsed 文档和 approved/converted 贡献才能抽取候选，候选需审核；但 admin/expert 可直接手工建正式节点。",
        "- 341 个 pending 候选显示质量/积压风险；缺批量语义去重与质量排序。",
        "- 比赛展示可用，但必须强调 PostgreSQL 轻量 KG，不宣称完整自动知识图谱学习。",
        "",
        "## 10. Diagnosis, SOP and Task Workflow Audit",
        "",
        "- 诊断输出原因、步骤、安全、建议、引用、history/media/KG 并写 diagnosis_records。",
        "- SOP 有步骤序号、expected result、safety、tools、materials、维护等级、版本、执行记录。",
        "- 安全文本覆盖断电、验电、挂牌、监护与 PPE 类工具；缺显式 prerequisite、prohibited_actions、stop_conditions schema。",
        "- SOP execution 支持 not_started -> in_progress -> completed/aborted，不能逆转。",
        "- 任务 create/assign/start/complete/cancel、来源 trace、SOP/执行、媒体/维护记录可关联。",
        "- Agent 草稿需要人工审批和显式转换，不自动执行高风险写操作；并发转换 5 请求只成功 1 条。",
        "",
        "## 11. Feedback and Correction Loop Audit",
        "",
        "- correction create/list/detail/resolve、source trace、before/after 和审核人可追踪。",
        "- 数据库 accepted=8，但 converted_contribution_id 全为空。",
        "- 未发现 accepted correction 自动/显式回用于 retrieval index、规则库或 prompt 版本。",
        "- 结论：记录闭环 verified，学习/回用闭环 missing；Task 25C 优先。",
        "",
        "## 12. Security Audit",
        "",
        "- JWT/RBAC、上传安全、日志脱敏、请求体限制、进程内 rate limit、production config guard 已实现。",
        "- 40 项 RBAC、11 项上传、日志脱敏和 secret scan 当前通过/附注。",
        "- secret scan：3 个本机 .env configured note、0 blocking，未输出值；历史已暴露密钥仍必须轮换。",
        "- development 当前 secret/admin password 未达生产标准；production guard 可拒绝弱配置。",
        "- operation_logs=0，说明统一审计日志并未覆盖所有业务；专项 event/call/review 表存在但缺保留/防篡改策略。",
        "- 进程内 rate limit 不适合多实例；本轮未做 429 专项行为测试。",
        "",
        "## 13. Performance Baseline",
        "",
        f"- 端点：12；请求：{performance['overall']['requests']}；错误率：{performance['overall']['error_rate']}。",
        f"- 总体 p50={performance['overall']['p50_ms']} ms，p95={performance['overall']['p95_ms']} ms，p99={performance['overall']['p99_ms']} ms，max={performance['overall']['max_ms']} ms。",
        f"- record center 串行 p95={endpoint['record_center']['serial']['p95_ms']} ms，并发 p95={endpoint['record_center']['concurrent']['p95_ms']} ms。",
        f"- KG context 串行 p95={endpoint['knowledge_graph_context']['serial']['p95_ms']} ms，并发 p95={endpoint['knowledge_graph_context']['concurrent']['p95_ms']} ms。",
        "- 实际参数为 warmup=1、serial=4、read concurrency=5；低于脚本默认 5/20/5，避免 120 req/min 限流污染。",
        "- 这不是四核 8GB/LoongArch 容量证明。日志表、JSONB、全表聚合、文件解析和 Agent 串行仍是风险。",
        "",
        "## 14. Testing and Quality Gates",
        "",
        "- compile、Alembic heads/current、13 个指定专项脚本、性能、npm audit/type/build、静态安装和 final smoke 均执行。",
        "- secret scan 首轮被新脚本参数名误报 blocking，修正局部变量名后重跑为 passed_with_notes；未放宽扫描器。",
        "- ruff/mypy 未配置；frontend 无 lint/type-check script，但 build 自带 vue-tsc，另执行 vue-tsc --noEmit。",
        "- 没有标准 pytest 套件；不能用 70 个专项脚本数量替代单元/服务/API 分层覆盖。",
        "- 现有 8 个浏览器脚本本轮未运行；LoongArch 测试缺失。",
        "",
        "## 15. LoongArch / Kylin Static Compatibility",
        "",
        "- 总结：high_risk，不是实机通过。",
        "- Python 风险：pydantic-core、greenlet、httptools、uvloop、watchfiles、lxml、libpq。",
        "- 前端风险：Vite 8/Rolldown lock 含平台二进制；建议预构建静态文件。",
        "- OCR/local model：Tesseract/language pack、llama.cpp/GGUF 必须目标机单独验证。",
        "- 部署风险：缺 .service/.conf，文件权限、SELinux/麒麟策略未知。",
        "",
        "## 16. Dead Code and Duplicate Code Candidates",
        "",
        f"- dead candidates：{len(dead['items'])}；duplicate candidates：{len(duplicate['items'])}；deprecated candidates：{len(deprecated['items'])}。",
        "- candidate：frontend 未引用 API/asset、历史 legacy/docs.zip、旧端口脚本、重复 repository CRUD/route response helper。",
        "- evidence：AST body hash、全局引用、router/menu/import、Git tracked/untracked、端口文本匹配。",
        "- confidence：仅 exact duplicate/high-confidence AST 可标 high；动态 adapter/router/model/frontend route 一律保守。",
        "- risk：静态扫描会漏字符串注册、__init__ metadata、动态 import 和兼容路由。",
        "- recommended action：Task 25H 逐项人工复核；本任务不处理候选，不触碰 migration。",
        "",
        "## 17. Enterprise Capability Gap",
        "",
        "| capability | status | gap |",
        "|---|---|---|",
        "| 高可用 | missing | 单实例、进程内限流、无 HA 演练 |",
        "| 备份恢复 | missing/P0 | 无正式脚本与恢复演练 |",
        "| 可观测性 | partial | status/log/trace 有；metrics/alert/tracing 无 |",
        "| 配置治理 | partial | pydantic settings/production guard 有；外部 secret store 无 |",
        "| 数据生命周期 | partial | archive 有；日志/媒体/候选保留策略无 |",
        "| 审计 | B | 专项审计表多；通用 operation_logs 未覆盖 |",
        "| 安全 | B | 基础门禁较好；token 撤销、secret rotation、多实例限流不足 |",
        "| 性能 | partial | 小样本可用；全表聚合和目标机容量未知 |",
        "| 可维护性 | partial | 分层好；重复/旧端口/候选多、无标准测试体系 |",
        "| 可扩展性 | B | adapter/agent registry 可扩展；真实 provider/索引生命周期未闭环 |",
        "",
        "## 18. Competition Demonstration Readiness",
        "",
        "- 可展示：登录/RBAC、文档/切片/审核、真实关键词 references、诊断、SOP、任务、记录、KG、人工修正、Agent 审批/转换。",
        "- 有条件展示：历史 Cloud/MIMO/OCR real-call 只能展示持久化记录和审计证据，本轮不代表实时在线。",
        "- 不应宣称：真实 DashVector/Embedding、共享图文向量、相似图片检索、LoongArch/Kylin 实机、企业级 HA。",
        "- 当前演示就绪度：中。Windows 本地可复现，但零分硬门与核心检索竞争力未关闭。",
        "",
        "## 19. P0 / P1 / P2 Issues",
        "",
        "### P0",
        "",
        "1. LoongArch/Kylin 未实机验收，且缺 systemd/Nginx 产物；影响：零分风险；任务：25G。",
        "2. 真实 Embedding/DashVector/跨模态匹配缺失；影响：核心赛题要求不满足；任务：25B。",
        "3. 无检索/视觉准确率金标准；影响：无法证明精准语义检索和识别有效；任务：25B。",
        "4. 生产密钥/管理员密码治理未闭环、历史密钥需轮换；影响：安全事故；任务：25E/25G。",
        "5. 无备份恢复；影响：数据不可恢复；任务：25E/25G。",
        "6. SOP 显式中止/禁止/前置 gate 不完整；影响：电气作业安全；任务：25D。",
        "",
        "### P1",
        "",
        "1. Record center 全量聚合/内存分页；影响：数据增长后延迟和内存；任务：25E。",
        "2. correction accepted 不回流；影响：持续学习闭环不成立；任务：25C。",
        "3. 无真实 rerank/citation faithfulness；影响：检索竞争力和可信性；任务：25B。",
        "4. KG 候选积压、版本/冲突/质量分不足；影响：知识污染；任务：25C。",
        "5. 缺标准 pytest、当前浏览器与长期稳定性验收；影响：回归风险；任务：25E/25F。",
        "6. 工作树高度 dirty；影响：交付混入历史/构建产物；任务：25H。",
        "",
        "### P2",
        "",
        "1. README 有泛新能源/储能旧表述和旧端口；任务：25H。",
        "2. 重复函数/未引用文件/legacy 候选需复核；任务：25H。",
        "3. UI 技术术语密集、无当前视觉/无障碍走查；任务：25F。",
        "4. 缺 ruff/mypy/lint script；任务：25H。",
        "5. 日志/媒体/候选数据保留策略不足；任务：25E。",
        "",
        "## 20. Keep / Enhance / Refactor / Remove Candidate Matrix",
        "",
        "| module | decision | rationale |",
        "|---|---|---|",
        "| FastAPI/Vue/PostgreSQL/Alembic | KEEP | 主架构与真实持久化已验证 |",
        "| JWT/RBAC/上传安全/脱敏 | ENHANCE | 基础好，补 token/secret/多实例限流 |",
        "| 文档解析/切分 | LOCAL_REFACTOR | 增加结构保真和质量门 |",
        "| 关键词检索/references | KEEP + ENHANCE | 当前可信主线 |",
        "| Embedding/DashVector/hybrid/rerank | MAJOR_REFACTOR | 当前 D 级 |",
        "| 多模态/跨模态 | MAJOR_REFACTOR | OCR/视觉 B，跨模态 C/E |",
        "| KG/贡献 | ENHANCE | 已参与业务，补质量/版本/冲突 |",
        "| correction feedback | MAJOR_REFACTOR | 记录有、回用无 |",
        "| SOP/task | LOCAL_REFACTOR | 补结构化安全 gate |",
        "| record center | MAJOR_REFACTOR | 全量聚合性能风险 |",
        "| Agent approval/conversion | KEEP | 人工边界和并发防重已验证 |",
        "| legacy/重复/未引用候选 | REMOVE_CANDIDATE | 仅候选，Task 25H 复核后决定 |",
        "| 目标机部署产物 | REPLACE/ADD | 当前只有文档/脚本路线，需正式产物 |",
        "",
        "## 21. Final Judgment",
        "",
        "**选择 C：关键主链路重构。**",
        "",
        "依据：35 项已 verified，说明主架构和业务底座值得保留；但 3 项 placeholder/mock 与 5 项 missing 集中在真实向量、跨模态、评估、反馈回用、备份恢复等赛题/企业硬点，无法靠零散修补达标。后续按 25B -> 25C/25D -> 25E -> 25F -> 25G -> 25H 推进。",
        "",
        "## Audit Scope Appendix",
        "",
        f"- files inventoried：{file_inventory['summary']['files_inventoried']}",
        f"- backend production files：{categories.get('backend_production_code', 0)}",
        f"- frontend production files：{categories.get('frontend_production_code', 0)}",
        f"- scripts/check files：{categories.get('test_or_audit_script', 0) + categories.get('local_operations_script', 0) + categories.get('local_operations_or_smoke_script', 0)}",
        f"- docs：{categories.get('documentation', 0)}",
        f"- migrations：{categories.get('migration', 0)}",
        f"- untracked files in scope：{file_inventory['summary']['untracked_files_in_scope']}",
        f"- generated assets：{file_inventory['summary']['generated_assets']}",
        f"- code files / lines（含历史交付和构建产物分类）：{code_inventory['summary']['files']} / {code_inventory['summary']['lines']}",
        "- storage policy：目录与数量盘点，未读取用户内容。",
    ]
    return "\n".join(lines)


def main() -> int:
    file_inventory = load_json("project_file_inventory.json")
    code_inventory = load_json("project_code_inventory.json")
    dependencies = load_json("project_dependency_inventory.json")
    test_inventory_data = load_json("test_inventory.json")
    performance = load_json("performance_baseline.json")
    dead = load_json("dead_code_candidates.json")
    duplicate = load_json("duplicate_code_candidates.json")
    deprecated = load_json("deprecated_code_candidates.json")

    traceability = build_traceability()
    write_json(RUNTIME / "requirement_traceability.json", traceability)
    write_text(DOCS / "25A_competition_requirement_traceability_matrix.md", traceability_markdown(traceability))
    write_text(DOCS / "25A_loongarch_kylin_static_compatibility_audit.md", loongarch_report(dependencies))
    write_text(DOCS / "25A_test_coverage_and_quality_gate_report.md", test_report(test_inventory_data, performance))
    write_text(DOCS / "25A_refactoring_decision_and_roadmap.md", roadmap_report())
    write_text(
        DOCS / "25A_competition_compliance_and_global_code_audit_report.md",
        global_report(traceability, file_inventory, code_inventory, performance, dead, duplicate, deprecated),
    )

    output = {
        "status": "passed",
        "requirements": len(traceability["requirements"]),
        "maturity_summary": traceability["summary"],
        "documents": [
            "docs/25A_competition_compliance_and_global_code_audit_report.md",
            "docs/25A_competition_requirement_traceability_matrix.md",
            "docs/25A_loongarch_kylin_static_compatibility_audit.md",
            "docs/25A_test_coverage_and_quality_gate_report.md",
            "docs/25A_refactoring_decision_and_roadmap.md",
        ],
        "runtime": ".runtime/task25a/requirement_traceability.json",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
