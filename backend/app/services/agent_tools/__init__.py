from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool
from app.services.agent_tools.device_tools import DeviceHistoryTool, DeviceLookupTool
from app.services.agent_tools.diagnosis_tools import DiagnosisRuleEngineTool
from app.services.agent_tools.kg_tools import KGBusinessContextTool
from app.services.agent_tools.knowledge_tools import KnowledgeContributionDraftCreatorTool, KnowledgeSearchTool
from app.services.agent_tools.media_tools import MediaLookupTool, MediaMimoAnalysisTool, MediaOCRTool
from app.services.agent_tools.model_tools import CorrectionSubmitterTool, ModelGatewayChatTool
from app.services.agent_tools.record_tools import RecordCenterLookupTool
from app.services.agent_tools.safety_tools import HumanApprovalTool, SafetyGuardTool
from app.services.agent_tools.sop_tools import SOPGeneratorTool
from app.services.agent_tools.task_tools import TaskDraftCreatorTool


AGENT_TOOL_CLASSES = {
    cls.tool_name: cls
    for cls in [
        KnowledgeSearchTool,
        KGBusinessContextTool,
        DeviceLookupTool,
        DeviceHistoryTool,
        MediaLookupTool,
        MediaOCRTool,
        MediaMimoAnalysisTool,
        DiagnosisRuleEngineTool,
        SOPGeneratorTool,
        TaskDraftCreatorTool,
        KnowledgeContributionDraftCreatorTool,
        RecordCenterLookupTool,
        CorrectionSubmitterTool,
        SafetyGuardTool,
        HumanApprovalTool,
        ModelGatewayChatTool,
    ]
}

__all__ = [
    "AGENT_TOOL_CLASSES",
    "AgentToolExecutionContext",
    "AgentToolResult",
    "BaseAgentTool",
]
