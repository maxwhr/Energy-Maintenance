from __future__ import annotations


class EquipmentClassificationService:
    """Rule-based Huawei equipment taxonomy stored in metadata_json."""

    RULES = (
        ("energy_storage", ("luna2000", "energy storage", "ess", "battery")),
        ("power_optimizer", ("merc-", "optimizer", "module controller", "组件控制器")),
        ("smart_guard", ("smartguard", "smart guard", "备电盒")),
        ("data_logger", ("smartlogger", "data logger")),
        ("plant_controller", ("smartacu", "sppc", "spms", "smartmgc", "plant controller")),
        ("communication_device", ("smart dongle", "smartdongle", "usb-adapter", "communication", "wifi", "wlan", "rs485", "通信")),
        ("management_platform", ("fusionsolar", "smartpvms", "management system", "管理系统")),
        ("mobile_app", ("fusionsolar app", "sun2000 app", "mobile app")),
        ("pv_inverter", ("sun2000", "pv inverter", "solar inverter", "光伏控制器", "逆变器")),
    )

    @classmethod
    def classify(cls, *values: str | list[str] | None) -> list[str]:
        text = " ".join(
            " ".join(str(item) for item in value) if isinstance(value, list) else str(value or "")
            for value in values
        ).lower()
        categories = [category for category, terms in cls.RULES if any(term in text for term in terms)]
        return list(dict.fromkeys(categories)) or ["other"]
