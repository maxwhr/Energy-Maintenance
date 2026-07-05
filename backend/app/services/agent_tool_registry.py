from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AgentDefinition, AgentTool
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentDefinitionRead, AgentToolRead


DEFAULT_AGENT_DEFINITIONS = [
    {
        "agent_code": "multimodal_evidence_agent",
        "agent_name": "多模态证据智能体",
        "agent_type": "multimodal_evidence",
        "description": "整理媒体证据、OCR 结果和人工描述的 dry-run 智能体，mimo-2.5 外部分析仍为预留能力。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {"default_tools": ["media_lookup", "media_ocr", "media_mimo_analysis", "safety_guard"]},
        "safety_policy_json": {"mode": "dry_run", "requires_approval_for_write": True},
        "metadata_json": {"scope": "Huawei/Sungrow PV inverter evidence assistance"},
    },
    {
        "agent_code": "retrieval_qa_agent",
        "agent_name": "检索问答智能体",
        "agent_type": "retrieval_qa",
        "description": "围绕已入库知识片段进行来源追溯式检修问答编排。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {"default_tools": ["knowledge_search", "kg_business_context", "record_center_lookup"]},
        "safety_policy_json": {"mode": "dry_run"},
        "metadata_json": {"scope": "source-traceable retrieval QA"},
    },
    {
        "agent_code": "fault_diagnosis_agent",
        "agent_name": "故障诊断智能体",
        "agent_type": "fault_diagnosis",
        "description": "编排规则诊断、知识检索和安全提示，输出初步诊断建议。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {"default_tools": ["diagnosis_rule_engine", "knowledge_search", "safety_guard"]},
        "safety_policy_json": {"mode": "dry_run", "must_include_safety_notes": True},
        "metadata_json": {"scope": "PV inverter fault diagnosis assistance"},
    },
    {
        "agent_code": "sop_planner_agent",
        "agent_name": "SOP 编排智能体",
        "agent_type": "sop_planner",
        "description": "根据故障和知识来源生成 SOP 草案，不直接执行现场作业。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {"default_tools": ["sop_generator", "safety_guard", "knowledge_search"]},
        "safety_policy_json": {"mode": "dry_run", "artifact_only": True},
        "metadata_json": {"scope": "SOP draft planning"},
    },
    {
        "agent_code": "task_orchestration_agent",
        "agent_name": "工单编排智能体",
        "agent_type": "task_orchestration",
        "description": "生成检修任务草案，高风险写入必须经过人工审批。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {"default_tools": ["task_draft_creator", "device_lookup", "human_approval"]},
        "safety_policy_json": {"mode": "dry_run", "write_requires_approval": True},
        "metadata_json": {"scope": "maintenance task draft orchestration"},
    },
    {
        "agent_code": "knowledge_curator_agent",
        "agent_name": "知识沉淀智能体",
        "agent_type": "knowledge_curator",
        "description": "生成知识贡献草案和人工修正建议，正式入库需审核。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {
            "default_tools": [
                "device_lookup",
                "device_history",
                "record_center_lookup",
                "knowledge_search",
                "kg_business_context",
                "media_lookup",
                "safety_guard",
                "knowledge_contribution_draft_creator",
                "human_approval",
            ]
        },
        "safety_policy_json": {"mode": "dry_run", "review_required": True},
        "metadata_json": {"scope": "knowledge curation draft"},
    },
    {
        "agent_code": "safety_guard_agent",
        "agent_name": "安全合规智能体",
        "agent_type": "safety_guard",
        "description": "对检修建议执行安全边界检查，强调不替代现场工程师和厂家手册。",
        "default_model_provider": "rule_based",
        "default_model_name": "rule_based_demo_agent_v1",
        "tool_policy_json": {"default_tools": ["safety_guard", "record_center_lookup"]},
        "safety_policy_json": {"mode": "dry_run", "electrical_safety_first": True},
        "metadata_json": {"scope": "safety guardrail"},
    },
]


DEFAULT_AGENT_TOOLS = [
    ("knowledge_search", "知识检索", "read", "检索已审核知识片段。", False, "low", ["admin", "expert", "engineer"]),
    ("kg_business_context", "知识图谱上下文", "read", "读取知识图谱业务上下文。", False, "low", ["admin", "expert", "engineer"]),
    ("media_lookup", "媒体证据查询", "read", "读取媒体证据元数据。", False, "low", ["admin", "expert", "engineer"]),
    ("media_ocr", "OCR 文本提取", "analysis", "读取已配置 OCR 能力或现有 OCR 结果。", False, "medium", ["admin", "expert", "engineer"]),
    (
        "media_mimo_analysis",
        "mimo-2.5 多模态分析",
        "analysis",
        "预留 mimo-2.5 多模态证据分析工具，当前外部配置缺失且禁用。",
        False,
        "high",
        ["admin", "expert", "engineer"],
    ),
    ("device_lookup", "设备查询", "read", "读取光伏逆变器台账信息。", False, "low", ["admin", "expert", "engineer"]),
    ("device_history", "维修履历查询", "read", "读取设备维修履历。", False, "low", ["admin", "expert", "engineer"]),
    ("diagnosis_rule_engine", "规则诊断", "analysis", "调用规则型故障诊断逻辑。", False, "medium", ["admin", "expert", "engineer"]),
    ("sop_generator", "SOP 生成", "generation", "生成 SOP 草案。", False, "medium", ["admin", "expert", "engineer"]),
    ("task_draft_creator", "任务草案生成", "generation", "生成检修任务草案。", True, "high", ["admin", "expert", "engineer"]),
    (
        "knowledge_contribution_draft_creator",
        "知识贡献草案生成",
        "generation",
        "生成知识贡献草案。",
        True,
        "high",
        ["admin", "expert", "engineer"],
    ),
    ("record_center_lookup", "记录中心查询", "read", "查询问答、诊断、任务、SOP 等追溯记录。", False, "low", ["admin", "expert", "engineer", "viewer"]),
    ("correction_submitter", "人工修正提交", "write", "提交模型输出修正建议。", True, "high", ["admin", "expert", "engineer"]),
    ("safety_guard", "安全合规检查", "safety", "执行电气检修安全提示与边界检查。", False, "medium", ["admin", "expert", "engineer", "viewer"]),
    ("human_approval", "人工审批", "approval", "记录人工审批结果。", True, "high", ["admin", "expert"]),
    ("model_gateway_chat", "模型网关对话", "analysis", "预留模型网关调用入口，默认使用规则兜底。", False, "medium", ["admin", "expert", "engineer"]),
]


class AgentToolRegistryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AgentRepository(db)

    def seed_defaults(self) -> dict[str, int]:
        definitions = 0
        tools = 0
        for values in DEFAULT_AGENT_DEFINITIONS:
            payload = {"enabled": True, **values}
            self.repository.upsert_definition(payload)
            definitions += 1
        for tool_name, display_name, tool_type, description, requires_approval, risk_level, roles in DEFAULT_AGENT_TOOLS:
            metadata_json = {
                "source": "agent_runtime_seed",
                "version": "v1",
                "execution_mode": "business_service_adapter",
                "formal_write_guard": "draft_only_until_human_approval" if requires_approval else "none",
                "external_api_called_by_default": False,
            }
            enabled = True
            if tool_name == "media_mimo_analysis":
                enabled = False
                metadata_json.update(
                    {
                        "requires_external_config": True,
                        "provider": "mimo_2_5",
                        "external_api_route_code": "agent_multimodal_mimo",
                        "status": "blocked",
                        "reason": "MIMO_API_KEY not configured; Task 22C gateway performs dry-run only",
                    }
                )
            if tool_name in {"task_draft_creator", "knowledge_contribution_draft_creator", "correction_submitter"}:
                metadata_json.update({"draft_only": True, "formal_business_record_created": False})
            if tool_name == "model_gateway_chat":
                metadata_json.update(
                    {
                        "default_provider": "rule_based",
                        "external_provider_required": False,
                        "external_api_route_code": "agent_model_chat",
                    }
                )
            if tool_name == "media_ocr":
                metadata_json.update(
                    {
                        "uses_existing_ocr_text_only_when_ocr_disabled": True,
                        "external_api_route_code": "agent_media_ocr",
                    }
                )
            if tool_name == "safety_guard":
                metadata_json.update({"external_api_route_code": "agent_safety_review"})
            self.repository.upsert_tool(
                {
                    "tool_name": tool_name,
                    "tool_display_name": display_name,
                    "tool_type": tool_type,
                    "description": description,
                    "enabled": enabled,
                    "requires_approval": requires_approval,
                    "allowed_roles_json": roles,
                    "input_schema_json": {"type": "object", "additionalProperties": True},
                    "output_schema_json": {"type": "object", "additionalProperties": True},
                    "risk_level": risk_level,
                    "metadata_json": metadata_json,
                }
            )
            tools += 1
        return {"definitions": definitions, "tools": tools}

    def list_definitions(self, *, enabled: bool | None = None) -> list[AgentDefinitionRead]:
        return [AgentDefinitionRead.model_validate(item) for item in self.repository.list_definitions(enabled=enabled)]

    def get_definition(self, agent_code: str) -> AgentDefinitionRead | None:
        item = self.repository.get_definition(agent_code)
        return AgentDefinitionRead.model_validate(item) if item else None

    def get_definition_model(self, agent_code: str) -> AgentDefinition | None:
        return self.repository.get_definition(agent_code)

    def list_tools(self, *, enabled: bool | None = None) -> list[AgentToolRead]:
        return [AgentToolRead.model_validate(item) for item in self.repository.list_tools(enabled=enabled)]

    def get_tools_by_name(self, tool_names: list[str]) -> list[AgentTool]:
        return [tool for name in tool_names if (tool := self.repository.get_tool(name))]
