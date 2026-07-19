#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
if ! id "${EM_SERVICE_USER}" >/dev/null 2>&1; then
  run useradd --system --home-dir "${EM_ROOT}" --shell /sbin/nologin "${EM_SERVICE_USER}"
fi
run install -d -m 0750 -o "${EM_SERVICE_USER}" -g "${EM_SERVICE_GROUP}" \
  "${EM_ROOT}" "${EM_RELEASES_DIR}" "${EM_SHARED_DIR}" "${EM_SHARED_DIR}/backups" \
  "${EM_DATA_DIR}/uploads" "${EM_DATA_DIR}/processed-media" "${EM_DATA_DIR}/tmp" "${EM_LOG_DIR}"
run install -d -m 0750 -o root -g "${EM_SERVICE_GROUP}" "$(dirname -- "${EM_CONFIG_FILE}")"
log "runtime directories initialized"

