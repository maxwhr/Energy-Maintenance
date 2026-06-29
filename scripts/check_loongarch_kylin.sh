#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check() {
  local name="$1"
  shift
  if "$@" >/tmp/energy-maintenance-check.out 2>&1; then
    echo "[passed] ${name}: $(tr '\n' ' ' </tmp/energy-maintenance-check.out | sed 's/[[:space:]]\+$//')"
  else
    echo "[warning] ${name}: command unavailable or failed"
  fi
}

echo "Energy-Maintenance LoongArch + Kylin environment check"
echo "Project: ${ROOT_DIR}"
echo "Architecture: $(uname -m 2>/dev/null || echo unknown)"

if [ -f /etc/os-release ]; then
  echo "OS: $(grep -E '^(NAME|VERSION)=' /etc/os-release | tr '\n' ' ')"
else
  echo "[warning] /etc/os-release not found"
fi

ARCH="$(uname -m 2>/dev/null || echo unknown)"
if [ "${ARCH}" = "loongarch64" ]; then
  echo "[passed] architecture is loongarch64"
else
  echo "[warning] architecture is ${ARCH}; final target should be loongarch64"
fi

if [ -f /etc/os-release ] && grep -Eiq 'kylin|银河麒麟' /etc/os-release; then
  echo "[passed] Kylin/Galaxy Kylin marker found in /etc/os-release"
else
  echo "[warning] Kylin marker not confirmed in /etc/os-release"
fi

check "python" python3 --version
check "pip" python3 -m pip --version
check "uv" uv --version
check "node" node --version
check "npm" npm --version
check "psql" psql --version
check "postgresql service" systemctl status postgresql
check "systemd" systemctl --version
check "nginx" nginx -v
check "gcc" gcc --version
check "make" make --version
check "cmake" cmake --version
check "tesseract" tesseract --version

if command -v llama-server >/dev/null 2>&1; then
  echo "[info] llama-server command exists; local llama.cpp is optional and must be validated separately."
else
  echo "[info] llama-server command not found; local llama.cpp/GGUF support remains optional."
fi

if command -v docker >/dev/null 2>&1; then
  echo "[info] docker command exists, but Docker is not the formal Energy-Maintenance deployment route."
else
  echo "[passed] docker is not required"
fi

[ -f "${ROOT_DIR}/backend/pyproject.toml" ] && echo "[passed] backend/pyproject.toml found" || echo "[failed] backend/pyproject.toml missing"
[ -f "${ROOT_DIR}/backend/alembic.ini" ] && echo "[passed] backend/alembic.ini found" || echo "[failed] backend/alembic.ini missing"
[ -f "${ROOT_DIR}/backend/static/frontend/index.html" ] && echo "[passed] static frontend installed" || echo "[warning] backend/static/frontend/index.html missing"

echo "This script does not install packages, execute migrations, or start services."
echo "llama.cpp / GGUF model service is optional and is not required by this environment check."
echo "If llama.cpp is enabled later, run: cd backend && uv run python scripts/check_local_llama_cpp_flow.py"
echo "Tesseract OCR is optional. If OCR is enabled later, run: scripts/check_tesseract_env.sh and backend/scripts/check_ocr_flow.py"
