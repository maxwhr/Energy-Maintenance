#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
base_url="${HEALTHCHECK_BASE_URL:-http://127.0.0.1:8012}"
if [[ "${base_url}" != "http://127.0.0.1:8012" && "${base_url}" != "http://localhost:8012" ]]; then
  die "health check is restricted to the local backend"
fi
if [[ "${DRY_RUN}" == "true" ]]; then
  run curl --fail --silent --show-error --max-time 10 "${base_url}/api/health"
  exit 0
fi
response="$(curl --fail --silent --show-error --max-time 10 "${base_url}/api/health")"
python3 -c 'import json,sys; payload=json.load(sys.stdin); assert payload.get("code")==200 and payload.get("data") is not None' <<<"${response}"
systemctl is-active --quiet energy-maintenance-backend.service || die "backend systemd service is not active"
nginx -t >/dev/null 2>&1 || die "Nginx configuration test failed"
[[ -L "${EM_CURRENT_LINK}" ]] || die "current release symlink is missing"
[[ -f "${EM_CURRENT_LINK}/frontend/index.html" ]] || die "frontend index.html is missing"
for directory in "${EM_DATA_DIR}/uploads" "${EM_DATA_DIR}/processed-media" "${EM_DATA_DIR}/tmp" "${EM_LOG_DIR}"; do
  [[ -w "${directory}" ]] || die "runtime directory is not writable: ${directory}"
done
available_kb="$(df -Pk "${EM_DATA_DIR}" | awk 'NR==2 {print $4}')"
[[ "${available_kb}" -gt 1048576 ]] || die "less than 1 GiB is available in the data filesystem"
pid="$(systemctl show --property MainPID --value energy-maintenance-backend.service)"
[[ "${pid}" =~ ^[1-9][0-9]*$ ]] || die "backend MainPID is unavailable"
rss_kb="$(awk '/VmRSS/ {print $2}' "/proc/${pid}/status")"
file_descriptors="$(find "/proc/${pid}/fd" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)"
restarts="$(systemctl show --property NRestarts --value energy-maintenance-backend.service)"
log "runtime rss_kb=${rss_kb:-unknown} file_descriptors=${file_descriptors} restarts=${restarts:-unknown} disk_available_kb=${available_kb}"
log "health check passed"
