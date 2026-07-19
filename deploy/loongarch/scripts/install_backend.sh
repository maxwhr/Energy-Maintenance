#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
release_id="${RELEASE_ID:-}"
source_backend="${SOURCE_BACKEND:-}"
wheelhouse="${WHEELHOUSE_DIR:-}"
for argument in "$@"; do
  case "${argument}" in
    --release-id=*) release_id="${argument#*=}" ;;
    --source-backend=*) source_backend="${argument#*=}" ;;
    --wheelhouse=*) wheelhouse="${argument#*=}" ;;
    --dry-run) ;;
    *) die "unknown argument: ${argument}" ;;
  esac
done
require_value "release id" "${release_id}"
require_value "source backend" "${source_backend}"
require_value "wheelhouse" "${wheelhouse}"
release_dir="${EM_RELEASES_DIR}/${release_id}"
[[ "${release_id}" =~ ^[A-Za-z0-9._-]+$ ]] || die "invalid release id"
[[ "${DRY_RUN}" == "true" || -d "${source_backend}" ]] || die "backend source directory not found"
[[ "${DRY_RUN}" == "true" || -d "${wheelhouse}" ]] || die "wheelhouse directory not found"
run install -d -m 0750 -o "${EM_SERVICE_USER}" -g "${EM_SERVICE_GROUP}" "${release_dir}/backend"
run cp -a "${source_backend}/." "${release_dir}/backend/"
if [[ "${DRY_RUN}" != "true" && ! -x "${EM_VENV_DIR}/bin/python" ]]; then
  run python3 -m venv "${EM_VENV_DIR}"
fi
requirements="${SCRIPT_DIR}/../requirements/requirements-loongarch.txt"
constraints="${SCRIPT_DIR}/../requirements/constraints-loongarch.txt"
run "${EM_VENV_DIR}/bin/python" -m pip install --no-index --find-links "${wheelhouse}" --constraint "${constraints}" --requirement "${requirements}"
run chown -R "${EM_SERVICE_USER}:${EM_SERVICE_GROUP}" "${release_dir}" "${EM_VENV_DIR}"
log "backend staged at ${release_dir}; current symlink is unchanged"
