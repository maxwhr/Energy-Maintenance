from types import SimpleNamespace

from scripts.check_task25g_loongarch_real_machine import validate_real_machine_guard


def test_windows_or_non_loongarch_cannot_pass_real_machine_guard(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    accepted, reasons = validate_real_machine_guard(allow=True)
    assert accepted is False
    assert "system_is_not_linux" in reasons
    assert "architecture_is_not_loongarch64" in reasons

