#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
required=(bash python3 psql nginx systemctl sha256sum curl)
missing=()
for command_name in "${required[@]}"; do
  command -v "${command_name}" >/dev/null 2>&1 || missing+=("${command_name}")
done
[[ "${#missing[@]}" -eq 0 ]] || die "missing system commands: ${missing[*]}"
log "system dependency commands are available"

