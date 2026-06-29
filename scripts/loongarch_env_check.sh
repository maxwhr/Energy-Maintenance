#!/usr/bin/env bash
set -u

echo "Energy-Maintenance LoongArch + Kylin environment check"
echo "This script is read-only. It does not install packages or change services."

check_cmd() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "[passed] ${name}: $(command -v "$cmd")"
  else
    echo "[failed] ${name}: ${cmd} not found"
  fi
}

arch="$(uname -m 2>/dev/null || echo unknown)"
os_name="$(cat /etc/os-release 2>/dev/null | grep -E '^PRETTY_NAME=' | cut -d= -f2- | tr -d '"' || echo unknown)"

echo "[info] os: ${os_name}"
echo "[info] arch: ${arch}"
case "${arch}" in
  loongarch64)
    echo "[passed] architecture is loongarch64"
    ;;
  *)
    echo "[warning] architecture is not loongarch64; this may be a development host"
    ;;
esac

check_cmd "python3" "python3"
check_cmd "pip" "pip3"
check_cmd "node" "node"
check_cmd "npm" "npm"
check_cmd "psql" "psql"
check_cmd "nginx" "nginx"
check_cmd "systemctl" "systemctl"

if command -v python3 >/dev/null 2>&1; then
  python3 --version
fi
if command -v node >/dev/null 2>&1; then
  node --version
fi
if command -v psql >/dev/null 2>&1; then
  psql --version
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl list-unit-files 2>/dev/null | grep -Ei 'postgres|nginx|energy-maintenance' || true
fi

echo "[info] formal deployment route: Python venv + native PostgreSQL + systemd + Nginx"
echo "[info] default model provider remains rule_based."
echo "[info] local_llama_cpp and cloud_openai require separate Task 14B/15 validation."
echo "[info] Docker is not the formal deployment route."
