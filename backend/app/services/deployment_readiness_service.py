from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any


class DeploymentReadinessService:
    """Build a sanitized, read-only deployment preparation summary."""

    ROOT = Path(__file__).resolve().parents[3]
    TASK25G_RUNTIME = ROOT / ".runtime" / "task25g"
    DEPLOY = ROOT / "deploy" / "loongarch"

    @classmethod
    def _read_json(cls, path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _artifact_status(value: dict[str, Any], *, missing: str = "NOT_AVAILABLE") -> str:
        status = value.get("status")
        return str(status) if status else missing

    @classmethod
    def collect(cls, *, role: str) -> dict[str, Any]:
        dependency = cls._read_json(cls.TASK25G_RUNTIME / "python_dependency_compatibility.json")
        native = cls._read_json(cls.TASK25G_RUNTIME / "native_dependency_risks.json")
        offline = cls._read_json(cls.TASK25G_RUNTIME / "offline_manifest_audit.json")
        real_machine = cls._read_json(cls.TASK25G_RUNTIME / "real_machine_acceptance.json")
        task25c = cls._read_json(cls.ROOT / ".runtime" / "task25c" / "acceptance_results.json")
        task25c_gate = cls._read_json(cls.ROOT / ".runtime" / "task25c" / "multimodal_quality_gate.json")
        r6 = cls._read_json(cls.ROOT / ".runtime" / "task25c" / "r6_deferred_status.json")
        rag = cls._read_json(cls.ROOT / ".runtime" / "task25f_r1" / "result.json")
        risks = native.get("risks") if isinstance(native.get("risks"), list) else []
        risk_categories: dict[str, int] = {}
        for risk in risks:
            category = str(risk.get("category") or "UNKNOWN")
            risk_categories[category] = risk_categories.get(category, 0) + 1

        machine = platform.machine().lower()
        system = platform.system().lower()
        payload: dict[str, Any] = {
            "platform": system,
            "architecture": machine,
            "os_family": "windows" if system == "windows" else ("kylin" if "kylin" in platform.platform().lower() else system),
            "deployment_mode": "native_systemd_nginx_postgresql",
            "docker_required": False,
            "systemd_template_available": (cls.DEPLOY / "config" / "energy-maintenance-backend.service").is_file(),
            "nginx_template_available": (cls.DEPLOY / "config" / "nginx-energy-maintenance.conf").is_file(),
            "offline_manifest_available": (cls.DEPLOY / "manifests" / "offline_requirements.json").is_file(),
            "python_dependency_audit": {
                "status": cls._artifact_status(dependency),
                "dependencies": int(dependency.get("dependency_count") or 0),
                "native_classification_coverage": dependency.get("native_classification_coverage"),
            },
            "native_dependency_risks": {
                "status": cls._artifact_status(native),
                "count": len(risks),
                "categories": risk_categories,
            },
            "real_machine_acceptance": {
                "status": "PENDING" if system == "windows" or machine != "loongarch64" else cls._artifact_status(real_machine, missing="PENDING"),
                "executed": bool(real_machine.get("executed")) if system != "windows" and machine == "loongarch64" else False,
            },
            "task25c_status": {
                "regression": str((task25c.get("results") or {}).get("task25c_regression") or "NOT_AVAILABLE"),
                "quality_gate": str((task25c.get("results") or {}).get("quality_gate") or task25c_gate.get("status") or "NOT_AVAILABLE"),
            },
            "r6_status": str(r6.get("status") or "NOT_AVAILABLE"),
            "rag_performance_status": str(rag.get("status") or "NOT_AVAILABLE"),
            "full_reindex_status": "DISABLED_NOT_EXECUTED",
            "offline_manifest_status": cls._artifact_status(offline),
        }
        if role == "admin":
            payload["native_dependency_risks"]["items"] = [
                {
                    "name": str(item.get("name") or "unknown"),
                    "category": str(item.get("category") or "UNKNOWN"),
                    "required": bool(item.get("required")),
                    "action": str(item.get("action") or item.get("reason") or "manual review required"),
                }
                for item in risks
            ]
            payload["python_dependency_audit"]["banned_production_dependencies"] = list(dependency.get("banned_production_dependencies") or [])
        return payload

