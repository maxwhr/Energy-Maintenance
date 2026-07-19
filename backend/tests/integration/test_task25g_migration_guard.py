import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_migration_backs_up_first_and_only_upgrades_to_head():
    text = (ROOT / "deploy/loongarch/scripts/migrate_database.sh").read_text(encoding="utf-8")
    backup_index = text.index('"${SCRIPT_DIR}/backup_before_upgrade.sh"')
    upgrade_index = text.index("upgrade head")
    assert backup_index < upgrade_index
    assert "20260712_0015" in (ROOT / "deploy/loongarch/lib/common.sh").read_text(encoding="utf-8")
    assert not re.search(r"alembic[^\n]*downgrade", text, re.IGNORECASE)
