#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
[[ -r "${EM_CONFIG_FILE}" || "${DRY_RUN}" == "true" ]] || die "environment file is not readable"
release_backend="${RELEASE_BACKEND:-${EM_CURRENT_LINK}/backend}"
"${SCRIPT_DIR}/backup_before_upgrade.sh" "$@"
if [[ "${DRY_RUN}" == "true" ]]; then
  run "${EM_VENV_DIR}/bin/python" -m alembic -c "${release_backend}/alembic.ini" upgrade head
  exit 0
fi
set -a
# shellcheck disable=SC1090
source "${EM_CONFIG_FILE}"
set +a
current="$(${EM_VENV_DIR}/bin/python -m alembic -c "${release_backend}/alembic.ini" current)"
log "database revision before upgrade: ${current:-none}"
run "${EM_VENV_DIR}/bin/python" -m alembic -c "${release_backend}/alembic.ini" upgrade head
after="$(${EM_VENV_DIR}/bin/python -m alembic -c "${release_backend}/alembic.ini" current)"
[[ "${after}" == *"${EM_EXPECTED_REVISION}"* ]] || die "unexpected revision after migration"
log "database migration reached ${EM_EXPECTED_REVISION}; no downgrade was attempted"

