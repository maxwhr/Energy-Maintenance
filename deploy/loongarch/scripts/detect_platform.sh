#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
parse_dry_run "$@"
machine="$(uname -m)"
static_only="false"
case "${machine}" in
  loongarch64) ;;
  x86_64|aarch64)
    if [[ " $* " == *" --allow-static-platform "* ]]; then
      static_only="true"
    else
      die "${machine} is supported only for static checks; target deployment requires loongarch64"
    fi
    ;;
  *) die "unsupported architecture: ${machine}" ;;
esac
[[ -r /etc/os-release ]] || die "/etc/os-release is unavailable"
# shellcheck disable=SC1091
source /etc/os-release
identity="${ID:-} ${NAME:-} ${ID_LIKE:-}"
if [[ "${static_only}" == "false" && "${identity,,}" != *kylin* ]]; then
  die "expected a Kylin OS identity"
fi
glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null || printf unavailable)"
python_version="$(python3 --version 2>&1 || printf unavailable)"
postgres_version="$(psql --version 2>&1 || printf unavailable)"
openssl_version="$(openssl version 2>&1 || printf unavailable)"
systemd_version="$(systemctl --version 2>&1 | head -n 1 || printf unavailable)"
nginx_version="$(nginx -v 2>&1 || printf unavailable)"
disk_available="$(df -Pk / | awk 'NR==2 {print $4}')"
memory_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || printf unavailable)"
cpu_cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf unavailable)"
locale_value="$(locale charmap 2>/dev/null || printf unavailable)"
timezone_value="$(date +%Z%z)"
root_status="false"
[[ "${EUID}" -eq 0 ]] && root_status="true"
service_user_exists="false"
id "${EM_SERVICE_USER}" >/dev/null 2>&1 && service_user_exists="true"
case_probe="$(mktemp -d)"
cleanup_case_probe() { rm -f -- "${case_probe}/task25g-case"; rmdir -- "${case_probe}"; }
trap cleanup_case_probe EXIT
touch "${case_probe}/task25g-case"
case_sensitive="true"
[[ -e "${case_probe}/TASK25G-CASE" ]] && case_sensitive="false"
log "platform=${machine} static_only=${static_only} os=${ID:-unknown} version=${VERSION_ID:-unknown}"
log "glibc=${glibc} python=${python_version} postgresql=${postgres_version} openssl=${openssl_version}"
log "systemd=${systemd_version} nginx=${nginx_version} disk_kb=${disk_available} memory_kb=${memory_kb} cpu=${cpu_cores}"
log "locale=${locale_value} timezone=${timezone_value} root=${root_status} service_user=${service_user_exists} case_sensitive=${case_sensitive}"
