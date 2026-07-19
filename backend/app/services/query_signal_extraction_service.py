from __future__ import annotations

import re
import unicodedata

from app.schemas.query_understanding import QuerySignals


class QuerySignalExtractionService:
    """Extract user-explicit facts before any model call.

    These values are authoritative user signals. An LLM may normalize their
    spelling but may not replace or invent them.
    """

    SUN2000_MODEL_RE = re.compile(
        r"(?<![A-Za-z0-9])SUN\s*[-_]?\s*2000"
        r"(?:[-_/ ]+\d{1,4}[A-Za-z]{1,8}\d*)?"
        r"(?:\s*[-_/]\s*[A-Za-z0-9]{1,12}){0,3}"
        r"(?:\s+[A-Za-z]{1,4}\d{1,4}){0,2}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    OTHER_MODEL_RE = re.compile(
        r"(?<![A-Za-z0-9])(?:LUNA2000|SmartLogger)(?:[-_/ ]?[A-Za-z0-9]{1,16}){0,4}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    EXPLICIT_ALARM_RE = re.compile(
        r"(?:告警(?:代码|码|ID)?|故障(?:代码|码)|报警(?:代码|码)?)\s*[：:=#]?\s*([A-Za-z]{0,4}-?\d{3,6})",
        re.IGNORECASE,
    )
    QUOTED_ALARM_NAME_RE = re.compile(r"[“\"「]([^”\"」]{2,40})[”\"」](?:故障)?告警")
    ALARM_NAME_RE = re.compile(r"([\u4e00-\u9fffA-Za-z0-9_-]{2,24})(?:故障)?告警")
    CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]{1,4}-?\d{3,6})(?![A-Za-z0-9])")
    NUMERIC_CODE_RE = re.compile(r"(?<![A-Za-z0-9])\d{3,6}(?![A-Za-z0-9])")
    NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?:V|A|Hz|℃|°C|%|秒|分钟|小时)?", re.IGNORECASE)
    COMPONENTS = (
        "逆变器", "通信模块", "SmartLogger", "电池", "储能", "组串", "风扇", "指示灯", "显示屏",
        "网线", "端子", "连接器", "传感器", "控制器", "功率模块", "直流开关", "交流开关",
    )
    TIME_CONDITIONS = (
        "晚上", "夜间", "白天", "早上", "升级后", "重启后", "并网时", "并网后", "上电后", "下电后",
        "高温时", "低温时", "雨天", "通信恢复后", "告警发生时",
    )
    OPERATING_STATES = ("并网", "离网", "待机", "运行", "停机", "升级", "启动", "关机", "充电", "放电")
    NEGATIVE = ("不", "没有", "无法", "不能", "未", "无输出", "不上电", "不开机", "不亮", "没反应")
    COMMUNICATION = (
        "通信", "掉线", "离线", "联网", "网络", "网线", "RS485", "Modbus", "以太网", "串口",
        "4G", "WLAN", "WiFi", "Wi-Fi", "平台无数据", "平台没数据", "平台没有数据",
    )
    SYMPTOMS = (
        "没反应", "无法启动", "不能启动", "不上电", "不开机", "不发电", "无输出", "不亮", "闪烁",
        "通信中断", "通信失败", "连接失败", "掉线", "离线", "过温", "重启", "异常", "告警", "故障",
        "无数据", "屏幕无显示", "指示灯不亮", "状态异常",
    )
    REQUEST_PATTERNS = {
        "CAUSE": ("为什么", "为何", "啥原因", "什么原因", "原因", "怎么回事", "什么导致", "导致"),
        "ACTION": (
            "怎么办", "咋办", "咋整", "怎么处理", "如何处理", "怎么修", "排查", "咋排查", "怎么解决",
            "怎么查", "先查啥", "先查什么", "该从哪儿查", "应检查什么",
        ),
        "PROCEDURE": (
            "步骤", "怎么操作", "如何操作", "流程", "按什么顺序", "顺序操作", "如何更换", "如何配置",
            "如何恢复", "如何回收", "怎样换算", "如何换算", "怎么换算", "换算",
        ),
        "SAFETY": ("安全", "风险", "危险", "注意事项", "注意什么", "能否带电", "触电", "防护"),
        "PREREQUISITE": ("前提", "前置", "操作前", "开始前", "需要先", "需要准备", "准备什么", "先做什么", "先满足", "哪些条件"),
        "VERIFICATION": ("如何确认", "怎么确认", "咋确认", "如何验证", "怎么验证", "确认", "确认恢复", "是否恢复", "恢复了吗", "是否正常", "完成后", "处理完以后"),
        "CONFIGURATION": ("配置", "设置", "参数", "地址", "波特率", "协议"),
        "COMPONENT": ("相关部件", "哪个部件", "部件异常"),
        "DIAGNOSIS": ("这类现象", "现象该从哪", "从哪儿查"),
        "COMMUNICATION": ("老是掉线", "通信异常", "通信中断"),
        "ALARM_MEANING": ("表示什么", "什么状态", "属于什么状态", "告警含义", "含义"),
    }
    MANUFACTURER_ALIASES = ("华为", "huawei")
    FORMAL_SUPPORT_MESSAGE = "当前版本正式支持华为 SUN2000 系列光伏逆变器检修知识。"
    UNSUPPORTED_VENDOR_TERMS = (
        "阳光电源", "sungrow", "锦浪", "ginlong", "solis", "固德威", "goodwe",
        "古瑞瓦特", "growatt", "上能电气", "sineng",
    )
    KNOWN_NUMERIC_ALARM_CODES = {"103", "301", "318", "321", "322", "326", "400", "410", "2061", "2062"}
    GENERIC_RETRIEVAL_TERMS = {
        "huawei", "华为", "sun2000", "fusionsolar", "光伏", "逆变器", "光伏逆变器", "设备",
        "如何", "怎么", "怎样", "什么", "哪些", "是否", "能否", "应该", "需要", "可以",
        "当前", "其中", "这里", "这个", "那个", "表示", "属于", "相关", "要求", "处理",
        "排查", "检查", "确认", "设置", "查询", "进行", "时候", "哪里", "哪个", "一下",
    }
    DOMAIN_RETRIEVAL_TERMS = (
        "背板", "膨胀螺栓", "设备基础信息", "产品型号", "直流输入电压高", "开路电压", "串联配置",
        "绝缘阻抗", "对地短路", "绝缘不良", "短路位置百分比", "百分比", "疑似故障位置",
        "检测条件不满足", "单路光伏组串", "光伏组串", "通信断链", "自动关机", "判定时间",
        "通信恢复", "RS485-2", "保护时间", "异常噪声", "散热空间", "安装距离", "电网欠压",
        "电网过压", "交流侧环境告警", "红色快闪", "低电压穿越", "LVRT", "多峰扫描",
        "全局MPPT扫描", "遮挡", "功率最大值", "带电", "线缆", "绝缘工具", "防护用具",
        "下电", "直流电流", "交流端子排", "对地电压", "等待", "风扇", "清理异物", "更换风扇",
    )
    FINITE_NORMALIZATIONS = (
        ("通迅不上", "通信不上"),
        ("通讯不上", "通信不上"),
        ("通迅中断", "通信中断"),
        ("通讯中断", "通信中断"),
        ("通迅", "通信"),
        ("通讯", "通信"),
        ("低绝缘", "绝缘阻抗低"),
        ("温度太高", "过温"),
        ("温度过高", "过温"),
        ("功率上不去", "输出功率异常"),
    )
    FAULT_TERMS = (
        ("low_insulation_resistance", ("绝缘阻抗低", "绝缘阻抗", "绝缘低", "对地绝缘异常", "绝缘故障", "直流侧对地异常")),
        ("communication_interruption", ("通信中断", "通信断链", "通信恢复", "通信不上", "连接不上", "连接失败", "设备离线", "fusionsolar 离线")),
        ("over_temperature", ("过温", "温度过高", "散热异常", "散热空间", "风扇异常", "风扇", "降额运行")),
        ("mppt_abnormal", (
            "mppt 异常", "mppt效率低", "mppt 效率低", "组串功率异常", "输入功率异常",
            "mppt 多峰扫描", "多峰扫描", "全局mppt扫描",
        )),
        ("low_power_generation", ("发电量低", "输出功率异常")),
        ("grid_connection_fault", ("并网失败", "电网异常", "电网电压过高", "电网电压过低", "电网欠压", "电网过压", "低电压穿越", "电压异常", "频率异常", "孤岛", "脱网")),
        ("dc_abnormal", ("直流输入电压高", "直流输入异常", "直流侧异常", "组串输入异常")),
    )
    CANONICAL_SYMPTOMS_BY_FAULT = {
        "low_insulation_resistance": ("绝缘阻抗低", "绝缘阻抗", "绝缘故障"),
        "communication_interruption": ("通信中断", "通信断链", "通信不上", "设备离线", "RS485"),
        "over_temperature": ("过温", "温度过高", "散热异常", "散热空间", "风扇异常", "风扇"),
        "mppt_abnormal": ("MPPT异常", "MPPT", "组串功率异常", "多峰扫描", "全局MPPT扫描", "遮挡"),
        "low_power_generation": ("发电量低", "输出功率异常"),
        "grid_connection_fault": (
            "并网失败", "电网异常", "电压异常", "频率异常", "电网欠压", "电网过压",
            "交流侧环境告警", "红色快闪",
        ),
        "dc_abnormal": (
            "直流输入异常", "直流侧异常", "组串输入异常", "直流输入电压高", "DC输入电压高",
            "开路电压", "光伏组串", "组串",
        ),
    }

    @classmethod
    def normalize(cls, query: str) -> str:
        value = unicodedata.normalize("NFKC", query or "")
        value = re.sub(r"\s+", " ", value).strip()
        for source, target in cls.FINITE_NORMALIZATIONS:
            value = re.sub(re.escape(source), target, value, flags=re.IGNORECASE)
        value = cls.SUN2000_MODEL_RE.sub(lambda match: cls._normalize_model(match.group(0)), value)
        return value

    @classmethod
    def retrieval_terms(cls, query: str, *, limit: int = 96) -> list[str]:
        """Build bounded Chinese/identifier terms without relying on whitespace tokenization."""

        normalized = cls.normalize(query)
        output: list[str] = []

        def add(value: str) -> None:
            cleaned = value.strip(" -_/，。；：、？！?()（）[]【】\t\r\n").casefold()
            if len(cleaned) < 2 or cleaned in cls.GENERIC_RETRIEVAL_TERMS or cleaned in output:
                return
            output.append(cleaned)

        lowered = normalized.casefold()
        for term in cls.DOMAIN_RETRIEVAL_TERMS:
            if term.casefold() in lowered:
                add(term)
        for match in cls.SUN2000_MODEL_RE.finditer(normalized):
            model = cls._normalize_model(match.group(0))
            if model.upper() != "SUN2000":
                add(model)
        for value in cls.EXPLICIT_ALARM_RE.findall(normalized):
            add(value)
        for value in re.findall(r"[A-Za-z]+(?:[._/-]?[A-Za-z0-9]+)+|[A-Za-z]{2,}|\d{3,6}", normalized):
            add(value)
        for run in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
            for size in (8, 7, 6, 5, 4, 3, 2):
                if size > len(run):
                    continue
                for start in range(0, len(run) - size + 1):
                    add(run[start:start + size])
                    if len(output) >= limit:
                        return output
        return output[:limit]

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    def extract(self, query: str) -> QuerySignals:
        original = (query or "").strip()
        original_normalized = unicodedata.normalize("NFKC", original)
        original_normalized = re.sub(r"\s+", " ", original_normalized).strip()
        normalized = self.normalize(original)
        raw_sun_models = [match.group(0) for match in self.SUN2000_MODEL_RE.finditer(original_normalized)]
        raw_other_models = [match.group(0) for match in self.OTHER_MODEL_RE.finditer(original_normalized)]
        model_originals = [*raw_sun_models, *raw_other_models]
        models = [self._normalize_model(value) for value in model_originals]
        if not models:
            models = [self._normalize_model(match.group(0)) for match in self.OTHER_MODEL_RE.finditer(normalized)]
        models = self._unique(models)
        has_fusionsolar = "fusionsolar" in normalized.lower()
        manufacturer = "huawei" if (
            any(alias in normalized.lower() for alias in self.MANUFACTURER_ALIASES)
            or any(model.upper().startswith("SUN2000") for model in models)
            or has_fusionsolar
        ) else None
        product_family = (
            "SUN2000" if any(model.upper().startswith("SUN2000") for model in models)
            else "FusionSolar" if has_fusionsolar
            else None
        )
        model = models[0] if models else None
        model_confidence = 0.0
        if model:
            model_confidence = 0.75 if model.upper() == "SUN2000" else 0.98
        alarm_codes = self.EXPLICIT_ALARM_RE.findall(normalized)
        alarm_codes.extend(self.CODE_RE.findall(normalized))
        model_spans = [match.span() for match in self.SUN2000_MODEL_RE.finditer(normalized)]
        for match in self.NUMERIC_CODE_RE.finditer(normalized):
            if self._is_numeric_alarm_candidate(
                match.group(0), match.start(), match.end(), normalized,
                manufacturer=manufacturer, models=models, model_spans=model_spans,
            ):
                alarm_codes.append(match.group(0))
        model_tokens = {value.upper() for model in models for value in re.split(r"[-_/ ]+", model)}
        alarm_codes = [
            value.upper()
            for value in alarm_codes
            if value.upper() not in model_tokens
            and value.upper() not in {"RS232", "RS485"}
            and not value.upper().startswith(("SUN", "LUNA", "SMARTLOGGER"))
        ]
        alarm_names = [*self.QUOTED_ALARM_NAME_RE.findall(normalized), *self.ALARM_NAME_RE.findall(normalized)]
        generic_alarm_names = {
            "当前", "历史", "相关", "设备", "这个", "该", "产生", "触发", "出现", "查看", "全部", "所有", "声光",
        }
        alarm_names = [
            value.strip(" ，。；：、")
            for value in alarm_names
            if value.strip(" ，。；：、") not in generic_alarm_names
            and not value.strip(" ，。；：、").isdigit()
            and value.strip(" ，。；：、").upper() not in set(alarm_codes)
            and not any(value.endswith(prefix) for prefix in ("出现", "产生", "触发", "查看"))
        ]
        requested = [name for name, terms in self.REQUEST_PATTERNS.items() if any(term in normalized for term in terms)]
        communication = [term for term in self.COMMUNICATION if term.lower() in normalized.lower()]
        symptoms = [term for term in self.SYMPTOMS if term in normalized]
        components = [term for term in self.COMPONENTS if term.lower() in normalized.lower()]
        conditions = [term for term in self.TIME_CONDITIONS if term in normalized]
        states = [term for term in self.OPERATING_STATES if term in normalized]
        negatives = [term for term in self.NEGATIVE if term in normalized]
        fault_type = self._fault_type(normalized, alarm_codes)
        symptoms.extend(self.CANONICAL_SYMPTOMS_BY_FAULT.get(fault_type or "", ()))
        maintenance_intent = self._maintenance_intent(requested, alarm_codes)
        safety_risk = self._safety_risk(normalized, requested, fault_type)
        return QuerySignals(
            original_query=original,
            normalized_query=normalized,
            manufacturer=manufacturer,
            product_family=product_family,
            model=model,
            model_original=model_originals[0] if model_originals else None,
            model_confidence=model_confidence,
            alarm_code=alarm_codes[0].upper() if alarm_codes else None,
            fault_type=fault_type,
            maintenance_intent=maintenance_intent,
            safety_risk=safety_risk,
            device_models=self._unique(models),
            alarm_codes=self._unique(alarm_codes),
            alarm_names=self._unique(alarm_names),
            fault_codes=self._unique(alarm_codes),
            components=self._unique(components),
            time_conditions=self._unique(conditions),
            operating_states=self._unique(states),
            numbers=self._unique(self.NUMBER_RE.findall(normalized)),
            negative_expressions=self._unique(negatives),
            action_intent=[value for value in requested if value in {"ACTION", "PROCEDURE", "PREREQUISITE", "VERIFICATION", "COMPONENT"}],
            safety_intent=[value for value in requested if value == "SAFETY"],
            communication_terms=self._unique(communication),
            symptoms=self._unique(symptoms),
            requested_information=self._unique(requested),
        )

    @staticmethod
    def _normalize_model(value: str) -> str:
        compact = unicodedata.normalize("NFKC", value or "").strip()
        if re.match(r"(?i)^SUN\s*[-_]?\s*2000", compact):
            compact = re.sub(r"(?i)^SUN\s*[-_]?\s*2000", "SUN2000", compact)
            compact = re.sub(r"\s*[-_/]\s*|\s+", "-", compact).strip("-_/ ")
            return compact.upper()
        prefixes = {"sun2000": "SUN2000", "luna2000": "LUNA2000", "smartlogger": "SmartLogger"}
        value = re.sub(r"\s+", "-", compact).rstrip("-_/ ")
        lowered = value.lower()
        for prefix, canonical in prefixes.items():
            if lowered.startswith(prefix):
                return canonical + value[len(prefix):].upper()
        return value

    @classmethod
    def _is_numeric_alarm_candidate(
        cls,
        value: str,
        start: int,
        end: int,
        query: str,
        *,
        manufacturer: str | None,
        models: list[str],
        model_spans: list[tuple[int, int]],
    ) -> bool:
        if any(span_start <= start and end <= span_end for span_start, span_end in model_spans):
            return False
        before = query[max(0, start - 12):start]
        after = query[end:min(len(query), end + 12)]
        if re.match(r"\s*(?:V|A|Hz|W|kW|MW|kWh|%|℃|°C|年|月|日|页)", after, re.IGNORECASE):
            return False
        if re.search(r"第\s*$", before) and re.match(r"\s*页", after):
            return False
        if re.search(r"\d\s*[-/.]\s*$", before) or re.match(r"\s*[-/.]\s*\d", after):
            return False
        if value in cls.KNOWN_NUMERIC_ALARM_CODES:
            return True
        window = f"{before}{after}".lower()
        explicit_context = any(term in window for term in ("告警", "故障码", "告警码", "错误码", "报警", "code", "alarm"))
        return bool(explicit_context)

    @classmethod
    def unsupported_scope_reason(
        cls,
        query: str,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
    ) -> str | None:
        """Return a bounded first-version scope violation without retrieving evidence."""

        normalized = unicodedata.normalize("NFKC", query or "").casefold()
        normalized_manufacturer = str(manufacturer or "").strip().casefold()
        normalized_product = str(product_series or "").strip().casefold()
        if normalized_manufacturer and normalized_manufacturer not in cls.MANUFACTURER_ALIASES:
            return "unsupported_manufacturer"
        if normalized_product and normalized_product not in {"sun2000", "fusionsolar"}:
            return "unsupported_product_series"
        if any(term.casefold() in normalized for term in cls.UNSUPPORTED_VENDOR_TERMS):
            return "unsupported_manufacturer"
        if re.search(r"(?<![a-z0-9])sg\s*[-_]?\s*\d{2,4}[a-z0-9-]*(?![a-z0-9])", normalized):
            return "unsupported_sungrow_model"
        if "luna2000" in normalized:
            return "unsupported_luna2000_product"
        if "smartlogger" in normalized:
            return "unsupported_smartlogger_product"
        return None

    @classmethod
    def unsafe_request_reason(cls, query: str) -> str | None:
        """Detect explicit unsafe instructions without blocking safety queries."""

        normalized = unicodedata.normalize("NFKC", query or "").casefold()
        compact = re.sub(r"\s+", "", normalized)
        safety_explanation = any(term in compact for term in ("严禁", "禁止", "不得", "请勿", "不可"))
        safety_inquiry = any(
            term in compact
            for term in (
                "能否", "是否可以", "是否允许", "可以吗", "需要哪些防护",
                "安全措施", "防护措施", "有什么风险", "有哪些风险",
                "为什么不能", "为何禁止", "为什么严禁", "注意事项",
            )
        )
        if any(term in compact for term in ("忽略安全", "绕过绝缘", "强制并网")):
            return "unsafe_safety_bypass_request"
        if not (safety_explanation or safety_inquiry) and "带电" in compact and any(
            term in compact for term in ("拆", "拔", "接线", "更换", "触碰")
        ):
            return "unsafe_live_electrical_operation"
        if "未验电" in compact and any(term in compact for term in ("立即", "更换", "拆", "接线")):
            return "unsafe_operation_without_voltage_verification"
        if "湿手" in compact and any(term in compact for term in ("触碰", "操作", "测温")):
            return "unsafe_wet_contact_operation"
        if any(term in compact for term in ("伪造", "编造不存在")) and any(
            term in compact for term in ("告警", "故障码", "步骤", "资料")
        ):
            return "fabricated_maintenance_information_request"
        return None

    @classmethod
    def _fault_type(cls, normalized: str, alarm_codes: list[str]) -> str | None:
        lowered = normalized.lower()
        for fault_type, terms in cls.FAULT_TERMS:
            if any(term.lower() in lowered for term in terms):
                return fault_type
        return "alarm_code_query" if alarm_codes else None

    @staticmethod
    def _maintenance_intent(requested: list[str], alarm_codes: list[str]) -> str | None:
        for value in ("SAFETY", "PROCEDURE", "ACTION", "CAUSE", "VERIFICATION", "PREREQUISITE"):
            if value in requested:
                return value
        return "ALARM" if alarm_codes else None

    @staticmethod
    def _safety_risk(normalized: str, requested: list[str], fault_type: str | None) -> str:
        high_risk_terms = ("带电", "触电", "拆机", "开盖", "直流侧", "交流侧", "绝缘", "更换", "下电")
        if "SAFETY" in requested or any(term in normalized for term in high_risk_terms):
            return "high_electrical_risk"
        if fault_type in {"grid_connection_fault", "dc_abnormal", "low_insulation_resistance"}:
            return "elevated_electrical_risk"
        return "standard_electrical_risk"
