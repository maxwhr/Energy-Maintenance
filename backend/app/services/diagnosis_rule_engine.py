from __future__ import annotations

from dataclasses import dataclass


MODEL_PROVIDER = "rule_based"
MODEL_NAME = "diagnosis_rule_engine_v1"


FAULT_TYPE_ALIASES = {
    "low_insulation_resistance": "low_insulation",
    "over_temperature": "overtemperature",
    "fan_fault": "overtemperature",
    "communication_interruption": "communication_fault",
    "device_offline": "communication_fault",
    "mppt_abnormal": "mppt_low_power",
    "low_power_generation": "mppt_low_power",
    "grid_connection_fault": "grid_fault",
    "ac_overvoltage": "grid_fault",
    "ac_undervoltage": "grid_fault",
    "dc_abnormal": "grid_fault",
    "alarm_code_query": "unknown",
}


@dataclass
class DiagnosisRuleResult:
    fault_type: str
    diagnosis_summary: str
    possible_causes: list[str]
    inspection_steps: list[str]
    recommended_actions: list[str]
    safety_notes: list[str]


class DiagnosisRuleEngine:
    def analyze(
        self,
        *,
        fault_type: str | None,
        fault_description: str,
        observed_symptoms: list[str],
        media_texts: list[str],
    ) -> DiagnosisRuleResult:
        normalized_fault_type = self.normalize_fault_type(fault_type, fault_description, observed_symptoms, media_texts)
        rules = self._rules()[normalized_fault_type]
        summary = rules["summary"]
        if observed_symptoms:
            summary = f"{summary} 已结合现场症状进行初步归因，仍需以厂家手册和现场测试结果复核。"
        return DiagnosisRuleResult(
            fault_type=normalized_fault_type,
            diagnosis_summary=summary,
            possible_causes=list(rules["possible_causes"]),
            inspection_steps=list(rules["inspection_steps"]),
            recommended_actions=list(rules["recommended_actions"]),
            safety_notes=list(rules["safety_notes"]),
        )

    def normalize_fault_type(
        self,
        fault_type: str | None,
        fault_description: str,
        observed_symptoms: list[str],
        media_texts: list[str],
    ) -> str:
        raw_fault_type = (fault_type or "unknown").strip()
        if raw_fault_type and raw_fault_type != "unknown":
            return FAULT_TYPE_ALIASES.get(raw_fault_type, raw_fault_type)

        text = " ".join([fault_description, *observed_symptoms, *media_texts]).lower()
        if any(term in text for term in ["绝缘", "insulation", "漏电", "接地"]):
            return "low_insulation"
        if any(term in text for term in ["过温", "temperature", "fan", "风扇", "散热", "降额"]):
            return "overtemperature"
        if any(term in text for term in ["通信", "通讯", "离线", "offline", "rs485", "network"]):
            return "communication_fault"
        if any(term in text for term in ["mppt", "功率低", "发电低", "遮挡", "组串", "current low"]):
            return "mppt_low_power"
        if any(term in text for term in ["电网", "并网", "grid", "过压", "欠压", "频率"]):
            return "grid_fault"
        return "unknown"

    @staticmethod
    def _rules() -> dict[str, dict[str, list[str] | str]]:
        common_safety = [
            "执行停送电和验电流程，确认直流侧、交流侧均处于安全作业状态后再开盖检查。",
            "佩戴绝缘手套、护目镜等电气防护用品，雨后或高湿环境下加强绝缘风险控制。",
            "现场处置不得绕过逆变器保护逻辑；无法确认风险时应升级厂家技术支持。",
        ]
        return {
            "low_insulation": {
                "summary": "当前故障更接近光伏逆变器直流侧绝缘偏低或接地泄漏风险，需要优先排查组件、组串线缆、接插件与潮湿环境影响。",
                "possible_causes": [
                    "光伏组串线缆破损、接插件进水或对地绝缘下降。",
                    "雨后高湿导致组件边框、汇流路径或接线端子绝缘性能降低。",
                    "逆变器绝缘检测回路、直流开关或接地连接存在异常。",
                ],
                "inspection_steps": [
                    "核对告警时间、天气湿度、并网前后状态和涉及的 MPPT/组串范围。",
                    "断开相关组串后分路测量对地绝缘电阻，定位异常组串。",
                    "检查组件背板、直流电缆、MC4 接头、汇流点和接地线是否破损、松动或受潮。",
                    "复位后观察绝缘阻值趋势，确认是否随湿度变化反复出现。",
                ],
                "recommended_actions": [
                    "更换破损线缆或进水接插件，对受潮端子进行干燥、防水和重新压接处理。",
                    "对异常组串建立复测记录，必要时隔离后逐步恢复并网。",
                    "若现场绝缘测量正常但告警持续，应导出设备日志并联系厂家复核检测回路。",
                ],
                "safety_notes": common_safety,
            },
            "overtemperature": {
                "summary": "当前故障更接近逆变器散热异常或环境温度过高导致的过温/降额，需要重点排查风道、风扇和安装环境。",
                "possible_causes": [
                    "进出风口堵塞、滤网积灰或安装间距不足导致散热不良。",
                    "风扇卡滞、转速异常或温度传感器读数异常。",
                    "环境温度过高、直射暴晒或长期满载运行触发降额保护。",
                ],
                "inspection_steps": [
                    "查看运行温度、负载功率、降额记录和过温告警发生时段。",
                    "检查风道、散热片、风扇运行声音和转速状态。",
                    "核对安装间距、遮阳条件和周边热源。",
                    "清洁散热通道后复测温升曲线。",
                ],
                "recommended_actions": [
                    "清理滤网、风道和散热片，恢复通风空间。",
                    "更换异常风扇或联系厂家校验温度采样部件。",
                    "对高温场景优化遮阳和通风，持续跟踪降额是否消除。",
                ],
                "safety_notes": common_safety,
            },
            "communication_fault": {
                "summary": "当前故障更接近通信链路中断或监控侧离线，需要同时检查逆变器端口、采集器、网络和平台配置。",
                "possible_causes": [
                    "RS485/以太网接线松动、屏蔽接地不良或通信地址冲突。",
                    "采集器供电、SIM/网络链路或 FusionSolar/监控平台配置异常。",
                    "逆变器通信模块、数据采集器或站内交换设备故障。",
                ],
                "inspection_steps": [
                    "确认逆变器本地运行状态与监控平台离线时间是否一致。",
                    "检查通信线缆、端子、地址、波特率、网关和采集器供电。",
                    "重启采集器或网络设备后观察链路恢复情况。",
                    "对比同站其他设备通信状态，判断是单机问题还是网络侧问题。",
                ],
                "recommended_actions": [
                    "紧固或更换异常通信线缆，修正地址和通信参数。",
                    "恢复采集器网络连接并同步监控平台配置。",
                    "若单机持续离线，导出日志并安排通信模块检测。",
                ],
                "safety_notes": common_safety,
            },
            "mppt_low_power": {
                "summary": "当前故障更接近 MPPT 支路发电偏低或组串不匹配，需要围绕组件遮挡、组串电压电流和接线一致性排查。",
                "possible_causes": [
                    "组件遮挡、积灰、热斑或组串数量/朝向不一致。",
                    "直流接插件松动、组串开路或支路电流偏低。",
                    "MPPT 参数异常或个别输入通道采样异常。",
                ],
                "inspection_steps": [
                    "比较各 MPPT 的电压、电流、功率曲线和同类设备发电表现。",
                    "现场检查遮挡、积灰、组件损伤、接插件和直流线缆状态。",
                    "用钳形表或组串测试仪核对异常支路电流。",
                    "在相近辐照条件下复核整改前后功率恢复情况。",
                ],
                "recommended_actions": [
                    "清理遮挡和积灰，修复异常接插件或开路支路。",
                    "调整不一致组串配置，确保同一路 MPPT 输入匹配。",
                    "持续异常时导出 I-V 或运行曲线给厂家分析。",
                ],
                "safety_notes": common_safety,
            },
            "grid_fault": {
                "summary": "当前故障更接近交流侧电网或并网条件异常，需要核对电压、频率、相序、断路器和并网参数。",
                "possible_causes": [
                    "交流电压越限、频率波动或电网质量异常。",
                    "交流断路器、接触器、端子或相序接线异常。",
                    "并网保护参数与现场电网要求不匹配。",
                ],
                "inspection_steps": [
                    "读取逆变器交流电压、频率、相序和并网保护告警。",
                    "测量并核对交流侧断路器、端子温升和接线紧固情况。",
                    "对比同站其他设备是否同时出现电网侧告警。",
                    "核对并网参数是否符合当地电网和厂家要求。",
                ],
                "recommended_actions": [
                    "修复交流侧接线、端子或断路器异常。",
                    "协调电网侧处理电压/频率越限问题。",
                    "按厂家和电网要求校核并网保护参数，保留调整记录。",
                ],
                "safety_notes": common_safety,
            },
            "unknown": {
                "summary": "当前故障类型不足以直接归类，系统提供通用的光伏逆变器安全排查路径，并建议补充告警码、运行日志和现场照片。",
                "possible_causes": [
                    "告警码、运行工况或现场症状信息不足，无法稳定归类。",
                    "可能涉及直流侧、交流侧、通信链路或散热部件的复合异常。",
                    "设备历史状态、环境变化或维护记录可能影响判断。",
                ],
                "inspection_steps": [
                    "补充厂家、型号、告警码、发生时间、天气和设备运行状态。",
                    "按直流侧、交流侧、通信侧、散热侧顺序做安全检查。",
                    "查询同设备历史记录，判断是否存在重复故障。",
                    "收集日志、照片和测量值后再进行专项诊断。",
                ],
                "recommended_actions": [
                    "优先完成安全隔离和信息补全，不直接进行带风险处置。",
                    "将现场数据与厂家手册和告警代码表交叉核对。",
                    "信息仍不足时升级给厂家或站内技术负责人复核。",
                ],
                "safety_notes": common_safety,
            },
        }
