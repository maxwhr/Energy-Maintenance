#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
[[ -r "${EM_CONFIG_FILE}" ]] || die "backend environment file is not readable"
mode="$(stat -c '%a' "${EM_CONFIG_FILE}")"
[[ "${mode}" == "640" || "${mode}" == "600" ]] || die "backend environment mode must be 0640 or 0600"
for directory in "${EM_DATA_DIR}/uploads" "${EM_DATA_DIR}/processed-media" "${EM_DATA_DIR}/tmp" "${EM_LOG_DIR}"; do
  [[ -d "${directory}" ]] || die "missing directory: ${directory}"
  owner="$(stat -c '%U:%G' "${directory}")"
  [[ "${owner}" == "${EM_SERVICE_USER}:${EM_SERVICE_GROUP}" ]] || die "unexpected owner for ${directory}"
done
log "permission checks passed"

