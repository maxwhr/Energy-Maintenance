from __future__ import annotations

from dataclasses import dataclass, field


SOP_RULE_ENGINE_NAME = "sop_rule_engine_v1"


@dataclass
class SOPRuleResult:
    title: str
    fault_type: str
    maintenance_level: str
    steps: list[dict]
    safety_requirements: list[dict]
    tools_required: list[dict]
    materials_required: list[dict]
    compliance_notes: str
    confidence: float = 0.55
    metadata: dict = field(default_factory=dict)


class SOPRuleEngine:
    def generate(
        self,
        *,
        manufacturer: str | None,
        product_series: str | None,
        model: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        maintenance_level: str,
        diagnosis_steps: list[str] | None = None,
        diagnosis_actions: list[str] | None = None,
    ) -> SOPRuleResult:
        normalized_fault_type = self.normalize_fault_type(fault_type)
        builder = {
            "low_insulation": self._low_insulation,
            "overtemperature": self._overtemperature,
            "communication_fault": self._communication_fault,
            "mppt_low_power": self._mppt_low_power,
            "grid_fault": self._grid_fault,
            "alarm_code_query": self._alarm_code_query,
        }.get(normalized_fault_type, self._unknown)

        result = builder(
            manufacturer=manufacturer,
            product_series=product_series,
            model=model,
            alarm_code=alarm_code,
            maintenance_level=maintenance_level,
        )
        result.steps = self._merge_diagnosis_guidance(result.steps, diagnosis_steps, diagnosis_actions)
        result.metadata["engine_name"] = SOP_RULE_ENGINE_NAME
        result.metadata["input_fault_type"] = fault_type
        return result

    @staticmethod
    def normalize_fault_type(fault_type: str | None) -> str:
        value = (fault_type or "unknown").strip()
        mapping = {
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
        }
        return mapping.get(value, value if value else "unknown")

    def _low_insulation(self, **context) -> SOPRuleResult:
        return SOPRuleResult(
            title=self._title(context, "低绝缘阻抗排查 SOP"),
            fault_type="low_insulation",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "作业前安全确认", "确认逆变器停机条件、现场隔离措施和个人防护用品，禁止带电拆接直流侧连接器。", "具备安全作业条件", "直流侧存在高压风险，必须执行两人复核。"),
                self._step(2, "核对告警信息", "在监控平台和设备面板核对绝缘阻抗告警、组串编号、发生时间和重复次数。", "告警对象与现场设备一致"),
                self._step(3, "检查直流侧连接", "逐路检查 PV 组串端子、汇流箱出线、接插件密封和电缆破损痕迹。", "发现受潮、破损或松动点位并记录"),
                self._step(4, "测量绝缘电阻", "按厂家手册要求使用合规绝缘测试仪测量组串对地绝缘电阻。", "绝缘阻值满足厂家阈值或定位异常组串"),
                self._step(5, "恢复与复检", "处理异常点后恢复接线，清除告警并观察逆变器并网和发电状态。", "告警不再出现且运行参数稳定"),
            ],
            safety_requirements=self._default_safety(extra="绝缘测试前必须确认被测回路与逆变器可靠隔离。"),
            tools_required=self._default_tools(["绝缘电阻测试仪", "万用表"]),
            materials_required=self._default_materials(["防水接插件", "绝缘胶带", "电缆标识牌"]),
            compliance_notes="按厂家逆变器手册、站内电气安全规程和停送电许可流程执行。",
            confidence=0.66,
        )

    def _overtemperature(self, **context) -> SOPRuleResult:
        return SOPRuleResult(
            title=self._title(context, "过温与风扇异常处理 SOP"),
            fault_type="overtemperature",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "确认运行环境", "检查设备周边通风距离、环境温度、遮挡物和柜体散热通道。", "散热环境满足安装要求"),
                self._step(2, "核对温度告警", "读取逆变器温度、功率降额记录和风扇运行状态。", "确认过温位置和触发时段"),
                self._step(3, "检查风扇和滤网", "停机后检查风扇转动、异响、积尘、滤网堵塞和端子连接。", "风扇和风道状态明确"),
                self._step(4, "清洁与更换", "清洁散热通道，必要时更换异常风扇或滤网。", "散热部件恢复正常"),
                self._step(5, "负载复检", "恢复运行后观察温度曲线、功率输出和是否再次降额。", "温度回落且无重复告警"),
            ],
            safety_requirements=self._default_safety(extra="风扇检修前必须确认旋转部件停止，避免误启动伤害。"),
            tools_required=self._default_tools(["红外测温仪", "绝缘手套", "清洁工具"]),
            materials_required=self._default_materials(["风扇组件", "滤网", "扎带"]),
            compliance_notes="禁止用水直接冲洗带电设备；清洁和更换件应符合厂家物料要求。",
            confidence=0.64,
        )

    def _communication_fault(self, **context) -> SOPRuleResult:
        return SOPRuleResult(
            title=self._title(context, "通信中断与离线恢复 SOP"),
            fault_type="communication_fault",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "确认离线范围", "核对单台逆变器离线、整串设备离线或站级平台通信异常。", "故障范围明确"),
                self._step(2, "检查供电与设备状态", "确认逆变器、数据采集器、交换机和通信电源运行状态。", "供电和设备状态正常或定位异常设备"),
                self._step(3, "检查通信链路", "检查 RS485、以太网、光纤或无线链路的端子、地址、波特率和网络连通性。", "链路配置和物理连接明确"),
                self._step(4, "恢复通信配置", "按厂家平台要求校验设备地址、协议、采集器绑定关系和时间同步。", "设备重新上线或异常原因明确"),
                self._step(5, "记录与观察", "记录通信恢复时间、离线时长和平台数据补传状态。", "平台数据连续且无重复离线"),
            ],
            safety_requirements=self._default_safety(extra="通信柜内仍可能存在交流供电，插拔线缆前确认端子标识。"),
            tools_required=self._default_tools(["网络测试仪", "万用表", "笔记本电脑"]),
            materials_required=self._default_materials(["通信线缆", "水晶头", "端子排"]),
            compliance_notes="通信参数修改应保留变更记录，避免影响同一链路其他设备。",
            confidence=0.63,
        )

    def _mppt_low_power(self, **context) -> SOPRuleResult:
        return SOPRuleResult(
            title=self._title(context, "MPPT 异常与低发电排查 SOP"),
            fault_type="mppt_low_power",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "比对发电数据", "比对同阵列同型号逆变器功率、MPPT 电压电流和日发电量。", "确认低发电是否明显偏离"),
                self._step(2, "检查组串输入", "检查异常 MPPT 下各组串电压、电流、接线极性和熔断器状态。", "异常组串或输入回路定位"),
                self._step(3, "排查遮挡与污染", "现场检查组件遮挡、积灰、热斑、破损和接线盒异常。", "组件侧影响因素明确"),
                self._step(4, "核验参数配置", "核对逆变器 MPPT 配置、组串接入数量和限功率设置。", "配置与设计一致"),
                self._step(5, "复核发电恢复", "处理后持续观察 MPPT 跟踪状态和功率恢复情况。", "功率恢复到同类设备合理区间"),
            ],
            safety_requirements=self._default_safety(extra="直流组串检查需防止反接、拉弧和带载插拔。"),
            tools_required=self._default_tools(["钳形表", "万用表", "红外热像仪"]),
            materials_required=self._default_materials(["组串保险", "接插件", "组件清洁耗材"]),
            compliance_notes="低发电判断应结合辐照、温度、限电和组件侧条件综合确认。",
            confidence=0.65,
        )

    def _grid_fault(self, **context) -> SOPRuleResult:
        return SOPRuleResult(
            title=self._title(context, "电网异常与并网故障处理 SOP"),
            fault_type="grid_fault",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "安全隔离确认", "确认交流侧开关状态、并网点许可和现场安全边界。", "满足交流侧检查条件", "交流侧存在触电和反送电风险。"),
                self._step(2, "核对电网告警", "读取过压、欠压、频率异常、相序异常或并网失败记录。", "告警类别和触发条件明确"),
                self._step(3, "测量交流参数", "测量并网点三相电压、频率、相序、接地和断路器状态。", "参数与厂家并网范围对齐"),
                self._step(4, "检查保护配置", "核对电网代码、保护阈值、功率因数和无功策略配置。", "配置符合电网和厂家要求"),
                self._step(5, "并网复检", "恢复后观察并网过程、功率爬升、告警复现和保护动作记录。", "并网稳定且无重复跳闸"),
            ],
            safety_requirements=self._default_safety(extra="交流参数测量需使用合格表计并执行监护制度。"),
            tools_required=self._default_tools(["万用表", "相序表", "绝缘手套"]),
            materials_required=self._default_materials(["断路器附件", "端子标识", "接地线材"]),
            compliance_notes="保护参数变更需按电网接入要求审批并留痕。",
            confidence=0.62,
        )

    def _alarm_code_query(self, **context) -> SOPRuleResult:
        alarm_code = context.get("alarm_code") or "未填写告警码"
        return SOPRuleResult(
            title=self._title(context, f"告警码 {alarm_code} 查询与处置 SOP"),
            fault_type="alarm_code_query",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "核对告警码", "在设备面板和监控平台核对告警码、告警名称、发生时间和恢复状态。", "告警码记录完整"),
                self._step(2, "查阅厂家资料", "优先查询已入库的厂家手册、告警代码表和故障案例。", "获取厂家建议的原因和处置方法"),
                self._step(3, "现场检查", "结合告警类型检查对应的直流侧、交流侧、通信侧或散热系统。", "完成针对性排查"),
                self._step(4, "处理与复位", "按厂家建议进行处理，确认具备复位条件后清除告警。", "告警清除且设备恢复运行"),
                self._step(5, "记录归档", "记录告警码、处置措施、复检结果和引用资料。", "形成可追溯记录"),
            ],
            safety_requirements=self._default_safety(extra="未确认告警含义前不得盲目复位保护或强制并网。"),
            tools_required=self._default_tools(["厂家手册", "万用表"]),
            materials_required=self._default_materials(["现场记录表"]),
            compliance_notes="告警处置应以厂家手册和站内操作票为准。",
            confidence=0.58,
        )

    def _unknown(self, **context) -> SOPRuleResult:
        return SOPRuleResult(
            title=self._title(context, "通用逆变器故障排查 SOP"),
            fault_type="unknown",
            maintenance_level=context["maintenance_level"],
            steps=[
                self._step(1, "确认安全条件", "确认设备状态、隔离措施、人员防护和作业许可。", "具备现场检查条件", "电气检修必须先做安全确认。"),
                self._step(2, "收集故障信息", "记录告警、运行参数、发生时段、天气和近期操作记录。", "形成完整故障背景"),
                self._step(3, "分系统排查", "按直流侧、交流侧、通信侧、散热系统和设备配置逐项排查。", "缩小故障范围"),
                self._step(4, "执行厂家建议", "查询厂家手册或告警代码资料，按建议处理并避免越权操作。", "处置过程有依据"),
                self._step(5, "复检归档", "恢复运行后观察关键参数并记录处置结果、遗留风险和引用资料。", "记录完整可追溯"),
            ],
            safety_requirements=self._default_safety(),
            tools_required=self._default_tools(["万用表", "绝缘手套", "现场记录工具"]),
            materials_required=self._default_materials(["端子标识", "扎带"]),
            compliance_notes="通用 SOP 仅用于初步作业指引，具体操作以厂家手册和现场安全规程为准。",
            confidence=0.48,
        )

    @staticmethod
    def _title(context: dict, suffix: str) -> str:
        parts = [context.get("manufacturer"), context.get("product_series"), context.get("model")]
        prefix = " ".join(str(part) for part in parts if part)
        return f"{prefix} {suffix}".strip()

    @staticmethod
    def _step(
        step_index: int,
        step_title: str,
        instruction: str,
        expected_result: str,
        safety_note: str | None = None,
    ) -> dict:
        return {
            "step_index": step_index,
            "step_title": step_title,
            "instruction": instruction,
            "expected_result": expected_result,
            "safety_note": safety_note,
        }

    @staticmethod
    def _default_safety(extra: str | None = None) -> list[dict]:
        items = [
            {"name": "停送电许可", "requirement": "执行站内停送电、验电、挂牌和监护要求。"},
            {"name": "个人防护", "requirement": "佩戴绝缘手套、安全帽、防护眼镜和符合等级的绝缘鞋。"},
            {"name": "厂家手册", "requirement": "关键拆装、复位和参数变更以厂家手册为准。"},
        ]
        if extra:
            items.append({"name": "专项风险", "requirement": extra})
        return items

    @staticmethod
    def _default_tools(extra: list[str] | None = None) -> list[dict]:
        tools = ["绝缘手套", "安全锁具", "现场记录终端"]
        if extra:
            tools.extend(extra)
        return [{"name": item, "requirement": "作业前确认完好并在有效期内"} for item in dict.fromkeys(tools)]

    @staticmethod
    def _default_materials(extra: list[str] | None = None) -> list[dict]:
        materials = ["警示牌", "设备标签"]
        if extra:
            materials.extend(extra)
        return [{"name": item, "requirement": "按现场实际需要准备"} for item in dict.fromkeys(materials)]

    @staticmethod
    def _merge_diagnosis_guidance(
        steps: list[dict],
        diagnosis_steps: list[str] | None,
        diagnosis_actions: list[str] | None,
    ) -> list[dict]:
        merged = list(steps)
        index = len(merged) + 1
        for text in (diagnosis_steps or [])[:2]:
            merged.append(
                {
                    "step_index": index,
                    "step_title": "结合诊断记录的排查补充",
                    "instruction": text,
                    "expected_result": "完成诊断记录建议的专项排查",
                    "safety_note": "与现场负责人确认该补充步骤适用于当前设备状态。",
                }
            )
            index += 1
        for text in (diagnosis_actions or [])[:2]:
            merged.append(
                {
                    "step_index": index,
                    "step_title": "结合诊断记录的处理补充",
                    "instruction": text,
                    "expected_result": "处理措施完成并具备复检条件",
                    "safety_note": "不得绕过厂家保护逻辑或现场审批流程。",
                }
            )
            index += 1
        return merged
