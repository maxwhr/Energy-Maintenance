#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
"${SCRIPT_DIR}/detect_platform.sh" "$@"
"${SCRIPT_DIR}/check_system_dependencies.sh" "$@"
"${SCRIPT_DIR}/check_python_runtime.sh" "$@"
"${SCRIPT_DIR}/check_native_dependencies.sh" "$@"
"${SCRIPT_DIR}/verify_offline_assets.sh" "$@"
log "preflight checks completed"

