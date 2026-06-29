#!/usr/bin/env bash
set -euo pipefail

# Example only. This script does not download llama.cpp, install packages, or provide a GGUF model.
# On LoongArch/Kylin, compile llama.cpp natively first, then adapt these local paths.
# Do not commit real model paths or model files.

LLAMA_SERVER="${LLAMA_SERVER:-/path/to/llama-server}"
MODEL_PATH="${MODEL_PATH:-/path/to/model.gguf}"
HOST_ADDRESS="${HOST_ADDRESS:-127.0.0.1}"
PORT="${PORT:-8080}"

echo "Energy-Maintenance llama.cpp example startup"
echo "This is only a template. Set LLAMA_SERVER and MODEL_PATH before running."

if [ ! -x "${LLAMA_SERVER}" ]; then
  echo "[blocked] llama-server is not executable: ${LLAMA_SERVER}"
  exit 1
fi

if [ ! -f "${MODEL_PATH}" ]; then
  echo "[blocked] GGUF model file not found: ${MODEL_PATH}"
  exit 1
fi

exec "${LLAMA_SERVER}" -m "${MODEL_PATH}" --host "${HOST_ADDRESS}" --port "${PORT}"
