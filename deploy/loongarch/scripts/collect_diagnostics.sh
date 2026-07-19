#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
output="${DIAGNOSTICS_OUTPUT:-${EM_LOG_DIR}/task25g-diagnostics.txt}"
if [[ "${DRY_RUN}" == "true" ]]; then
  run systemctl status energy-maintenance-backend.service --no-pager
  run nginx -t
  exit 0
fi
temporary="$(mktemp)"
cleanup() { rm -f -- "${temporary}"; }
trap cleanup EXIT
{
  printf 'generated_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'machine=%s\n' "$(uname -m)"
  printf 'python=%s\n' "$(python3 --version 2>&1)"
  printf 'current_release=%s\n' "$(readlink "${EM_CURRENT_LINK}" 2>/dev/null || printf unavailable)"
  systemctl status energy-maintenance-backend.service --no-pager || true
  journalctl -u energy-maintenance-backend.service --since '-30 minutes' --no-pager -n 200 || true
  nginx -t 2>&1 || true
} >"${temporary}"
sed -E 's#(postgresql[^:]*://)[^@ ]+@#\1[REDACTED]@#g; s#(SECRET|PASSWORD|TOKEN|API_KEY)=.*#\1=[REDACTED]#g' "${temporary}" >"${output}"
chmod 0640 "${output}"
log "sanitized diagnostics collected"

