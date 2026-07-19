#!/usr/bin/env bash
set -euo pipefail

umask 027

EM_ROOT="${EM_ROOT:-/opt/energy-maintenance}"
EM_RELEASES_DIR="${EM_RELEASES_DIR:-${EM_ROOT}/releases}"
EM_CURRENT_LINK="${EM_CURRENT_LINK:-${EM_ROOT}/current}"
EM_SHARED_DIR="${EM_SHARED_DIR:-${EM_ROOT}/shared}"
EM_VENV_DIR="${EM_VENV_DIR:-${EM_SHARED_DIR}/venv}"
EM_DATA_DIR="${EM_DATA_DIR:-/var/lib/energy-maintenance}"
EM_LOG_DIR="${EM_LOG_DIR:-/var/log/energy-maintenance}"
EM_CONFIG_FILE="${EM_CONFIG_FILE:-/etc/energy-maintenance/backend.env}"
EM_SERVICE_USER="${EM_SERVICE_USER:-energy-maintenance}"
EM_SERVICE_GROUP="${EM_SERVICE_GROUP:-energy-maintenance}"
EM_EXPECTED_REVISION="${EM_EXPECTED_REVISION:-20260712_0015}"
DRY_RUN="${DRY_RUN:-false}"

log() {
  printf '[task25g] %s\n' "$*"
}

die() {
  printf '[task25g] ERROR: %s\n' "$*" >&2
  exit 1
}

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '[task25g] DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

require_root() {
  if [[ "${DRY_RUN}" != "true" && "${EUID}" -ne 0 ]]; then
    die "this operation requires root; rerun with sudo or use --dry-run"
  fi
}

require_value() {
  local name="$1"
  local value="$2"
  [[ -n "${value}" ]] || die "${name} is required"
}

parse_dry_run() {
  for argument in "$@"; do
    case "${argument}" in
      --dry-run) DRY_RUN="true" ;;
      *) ;;
    esac
  done
}

task25g_trap() {
  local exit_code=$?
  if [[ "${exit_code}" -ne 0 ]]; then
    log "command failed with exit code ${exit_code}"
  fi
}

trap task25g_trap EXIT

