#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
require_root
backup_dir="${EM_SHARED_DIR}/backups/$(date -u +%Y%m%dT%H%M%SZ)"
run install -d -m 0750 -o "${EM_SERVICE_USER}" -g "${EM_SERVICE_GROUP}" "${backup_dir}"
if [[ "${DRY_RUN}" == "true" ]]; then
  run pg_dump --format=custom --file "${backup_dir}/database.dump" energy_maintenance
  exit 0
fi
[[ -r "${EM_CONFIG_FILE}" ]] || die "environment file is not readable"
set -a
# shellcheck disable=SC1090
source "${EM_CONFIG_FILE}"
set +a
export TASK25G_BACKUP_FILE="${backup_dir}/database.dump"
run sudo -u "${EM_SERVICE_USER}" --preserve-env=DATABASE_URL,TASK25G_BACKUP_FILE python3 - <<'PY'
import os
from urllib.parse import unquote, urlsplit

parsed = urlsplit(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1))
environment = os.environ.copy()
environment["PGHOST"] = parsed.hostname or "127.0.0.1"
environment["PGPORT"] = str(parsed.port or 5432)
environment["PGUSER"] = unquote(parsed.username or "")
environment["PGPASSWORD"] = unquote(parsed.password or "")
environment["PGDATABASE"] = parsed.path.lstrip("/")
os.execvpe("pg_dump", ["pg_dump", "--format=custom", "--file", os.environ["TASK25G_BACKUP_FILE"]], environment)
PY
if [[ -L "${EM_CURRENT_LINK}" ]]; then
  readlink "${EM_CURRENT_LINK}" >"${backup_dir}/current-release.txt"
fi
run chown -R "${EM_SERVICE_USER}:${EM_SERVICE_GROUP}" "${backup_dir}"
log "pre-upgrade backup created; credentials were not printed"
