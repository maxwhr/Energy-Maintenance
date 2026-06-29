#!/usr/bin/env bash
set -u

COMMAND="${TESSERACT_CMD:-tesseract}"
REQUIRED_LANGS="${OCR_REQUIRED_LANGS:-chi_sim eng}"

echo "Energy-Maintenance optional Tesseract OCR environment check"
echo "This script only checks the local environment. It does not install Tesseract or language packages."

if ! command -v "${COMMAND}" >/dev/null 2>&1; then
  echo "[blocked] tesseract command was not found in PATH"
  echo "status=not_configured"
  exit 0
fi

echo "[passed] command: $(command -v "${COMMAND}")"
if "${COMMAND}" --version >/tmp/energy-maintenance-tesseract-version.out 2>&1; then
  echo "[passed] version: $(head -n 1 /tmp/energy-maintenance-tesseract-version.out)"
else
  echo "[blocked] tesseract --version failed"
  echo "status=not_configured"
  exit 0
fi

if ! "${COMMAND}" --list-langs >/tmp/energy-maintenance-tesseract-langs.out 2>&1; then
  echo "[blocked] tesseract --list-langs failed"
  echo "status=not_configured"
  exit 0
fi

missing=""
for lang in ${REQUIRED_LANGS}; do
  if ! grep -qx "${lang}" /tmp/energy-maintenance-tesseract-langs.out; then
    missing="${missing} ${lang}"
  fi
done

if [ -n "${missing}" ]; then
  echo "[blocked] missing language packages:${missing}"
  echo "status=not_configured"
  exit 0
fi

echo "[passed] required language packages are visible: ${REQUIRED_LANGS}"
echo "status=available"
exit 0
