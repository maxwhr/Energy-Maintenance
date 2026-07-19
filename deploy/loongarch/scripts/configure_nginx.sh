#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
template="${SCRIPT_DIR}/../config/nginx-energy-maintenance.conf"
target="${NGINX_CONF_TARGET:-/etc/nginx/conf.d/energy-maintenance.conf}"
run install -m 0644 -o root -g root "${template}" "${target}"
run nginx -t
log "Nginx configuration installed and validated; Nginx was not reloaded"

