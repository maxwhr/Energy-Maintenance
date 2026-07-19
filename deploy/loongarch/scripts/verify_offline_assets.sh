#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
wheelhouse="${WHEELHOUSE_DIR:-${1:-}}"
[[ "${wheelhouse}" != "--dry-run" ]] || wheelhouse=""
if [[ "${DRY_RUN}" == "true" && -z "${wheelhouse}" ]]; then
  wheelhouse="/offline/wheelhouse-loongarch64"
fi
require_value "wheelhouse" "${wheelhouse}"
[[ "${DRY_RUN}" == "true" || -d "${wheelhouse}" ]] || die "wheelhouse directory not found"
if [[ "${DRY_RUN}" != "true" ]]; then
  while IFS= read -r -d '' wheel; do
    name="$(basename -- "${wheel}")"
    case "${name}" in
      *win_amd64*|*manylinux*x86_64*|*aarch64*|*macosx*) die "foreign wheel rejected: ${name}" ;;
      *-py3-none-any.whl|*loongarch64*.whl) ;;
      *) die "unrecognized wheel architecture tag: ${name}" ;;
    esac
  done < <(find "${wheelhouse}" -maxdepth 1 -type f -name '*.whl' -print0)
fi
log "offline wheel architecture policy passed"

