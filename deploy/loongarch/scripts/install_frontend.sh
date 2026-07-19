#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
release_id="${RELEASE_ID:-}"
frontend_dist="${FRONTEND_DIST:-}"
for argument in "$@"; do
  case "${argument}" in
    --release-id=*) release_id="${argument#*=}" ;;
    --frontend-dist=*) frontend_dist="${argument#*=}" ;;
    --dry-run) ;;
    *) die "unknown argument: ${argument}" ;;
  esac
done
require_value "release id" "${release_id}"
require_value "frontend dist" "${frontend_dist}"
[[ "${release_id}" =~ ^[A-Za-z0-9._-]+$ ]] || die "invalid release id"
[[ "${DRY_RUN}" == "true" || -f "${frontend_dist}/index.html" ]] || die "prebuilt frontend index.html missing"
target="${EM_RELEASES_DIR}/${release_id}/frontend"
run install -d -m 0750 -o "${EM_SERVICE_USER}" -g "${EM_SERVICE_GROUP}" "${target}"
run cp -a "${frontend_dist}/." "${target}/"
run chown -R "${EM_SERVICE_USER}:${EM_SERVICE_GROUP}" "${target}"
log "prebuilt frontend installed without Node.js or npm"

