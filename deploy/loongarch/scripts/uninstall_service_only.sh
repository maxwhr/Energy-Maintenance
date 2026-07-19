#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
run systemctl disable --now energy-maintenance-backend.service
run rm -f -- /etc/systemd/system/energy-maintenance-backend.service
run systemctl daemon-reload
log "service unit removed; releases, data, database, logs, config, and Nginx config were preserved"

