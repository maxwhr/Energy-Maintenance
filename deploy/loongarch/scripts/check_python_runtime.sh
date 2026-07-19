#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
python3 - <<'PY'
import platform
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
if platform.machine().lower() != "loongarch64":
    raise SystemExit("Python must execute natively on loongarch64")
print(f"python={platform.python_version()} implementation={platform.python_implementation()}")
PY

