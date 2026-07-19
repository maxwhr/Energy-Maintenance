#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
required=(gcc g++ make pkg-config rustc cargo pg_config)
missing=()
for command_name in "${required[@]}"; do
  command -v "${command_name}" >/dev/null 2>&1 || missing+=("${command_name}")
done
[[ "${#missing[@]}" -eq 0 ]] || die "native build tools missing: ${missing[*]}"
for library in libpq openssl libffi libjpeg libpng zlib; do
  pkg-config --exists "${library}" >/dev/null 2>&1 || log "review system library availability: ${library}"
done
log "native toolchain check completed; review warnings before wheel build"

