from scripts.check_task25g_loongarch_real_machine import validate_real_machine_guard


def test_real_machine_guard_requires_explicit_authorization(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "loongarch64")
    monkeypatch.setattr("scripts.check_task25g_loongarch_real_machine._os_release", lambda: "ID=kylin")
    accepted, reasons = validate_real_machine_guard(allow=False)
    assert accepted is False
    assert reasons == ["explicit_authorization_missing"]

