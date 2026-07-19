#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
template="${SCRIPT_DIR}/../config/energy-maintenance-backend.service"
run install -m 0644 -o root -g root "${template}" /etc/systemd/system/energy-maintenance-backend.service
run install -m 0644 -o root -g root "${SCRIPT_DIR}/../config/logrotate-energy-maintenance" /etc/logrotate.d/energy-maintenance
run systemctl daemon-reload
run systemctl enable energy-maintenance-backend.service
log "systemd unit installed; service was not started"
