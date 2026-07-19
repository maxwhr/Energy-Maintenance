from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_linux_runtime_scripts_do_not_call_windows_commands():
    for path in (ROOT / "deploy/loongarch/scripts").glob("*.sh"):
        text = path.read_text(encoding="utf-8").lower()
        assert "powershell" not in text
        assert "cmd.exe" not in text
        assert "npm.cmd" not in text

