#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
release_id="${RELEASE_ID:-}"
for argument in "$@"; do
  case "${argument}" in
    --release-id=*) release_id="${argument#*=}" ;;
    --dry-run) ;;
    *) die "unknown argument: ${argument}" ;;
  esac
done
require_value "release id" "${release_id}"
[[ "${release_id}" =~ ^[A-Za-z0-9._-]+$ ]] || die "invalid release id"
target="${EM_RELEASES_DIR}/${release_id}"
[[ "${DRY_RUN}" == "true" || -d "${target}/backend" ]] || die "release backend does not exist"
[[ "${DRY_RUN}" == "true" || -f "${target}/frontend/index.html" ]] || die "release frontend does not exist"
temporary="${EM_ROOT}/.current-${release_id}.tmp"
run ln -sfn "${target}" "${temporary}"
run mv -Tf "${temporary}" "${EM_CURRENT_LINK}"
run systemctl restart energy-maintenance-backend.service
run systemctl reload nginx.service
log "current symlink switched atomically; database downgrade was not executed"

