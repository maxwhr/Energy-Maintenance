from __future__ import annotations

import platform
from pathlib import Path
from typing import Any


class DeploymentReadinessService:
    """Build a sanitized summary from formal deployment files only."""

    ROOT = Path(__file__).resolve().parents[3]
    DEPLOY = ROOT / "deploy" / "loongarch"

    @classmethod
    def collect(cls, *, role: str) -> dict[str, Any]:
        machine = platform.machine().lower()
        system = platform.system().lower()
        dependency_configured = (cls.ROOT / "backend" / "pyproject.toml").is_file()
        offline_manifest = (
            cls.DEPLOY / "manifests" / "offline_requirements.json"
        ).is_file()

        payload: dict[str, Any] = {
            "platform": system,
            "architecture": machine,
            "os_family": (
                "windows"
                if system == "windows"
                else (
                    "kylin"
                    if "kylin" in platform.platform().lower()
                    else system
                )
            ),
            "deployment_mode": "native_systemd_nginx_postgresql",
            "docker_required": False,
            "systemd_template_available": (
                cls.DEPLOY
                / "config"
                / "energy-maintenance-backend.service"
            ).is_file(),
            "nginx_template_available": (
                cls.DEPLOY / "config" / "nginx-energy-maintenance.conf"
            ).is_file(),
            "offline_manifest_available": offline_manifest,
            "offline_manifest_status": (
                "available" if offline_manifest else "not_available"
            ),
            "python_dependency_audit": {
                "status": (
                    "configured" if dependency_configured else "not_configured"
                ),
                "dependencies": 0,
                "native_classification_coverage": None,
            },
            "native_dependency_risks": {
                "status": "not_evaluated",
                "count": 0,
                "categories": {},
            },
            "real_machine_acceptance": {
                "status": (
                    "ready_for_acceptance"
                    if system != "windows" and machine == "loongarch64"
                    else "pending"
                ),
                "executed": False,
            },
        }
        if role == "admin":
            payload["native_dependency_risks"]["items"] = []
            payload["python_dependency_audit"][
                "banned_production_dependencies"
            ] = []
        return payload
