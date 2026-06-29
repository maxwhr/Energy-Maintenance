#!/usr/bin/env bash
set -u

BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
USERNAME="${FULL_SMOKE_ADMIN_USERNAME:-admin}"
PASSWORD="${FULL_SMOKE_ADMIN_PASSWORD:-admin123456}"

PASSED=0
FAILED=0
TOKEN=""

tmp_files=()
cleanup() {
  for file in "${tmp_files[@]}"; do
    [ -f "$file" ] && rm -f "$file"
  done
}
trap cleanup EXIT

record_result() {
  local status="$1"
  local method="$2"
  local path="$3"
  local notes="${4:-}"
  if [ "$status" = "passed" ]; then
    PASSED=$((PASSED + 1))
  else
    FAILED=$((FAILED + 1))
  fi
  printf '[%s] %s %s %s\n' "$status" "$method" "$path" "$notes"
}

json_code_ok() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    sys.exit(1)

sys.exit(0 if payload.get("code") in (0, 200) else 1)
PY
}

extract_token() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    token = (payload.get("data") or {}).get("access_token") or ""
except Exception:
    token = ""
print(token)
sys.exit(0 if token else 1)
PY
}

test_web() {
  local name="$1"
  local path="$2"
  local status
  status="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 20 "${BASE_URL}${path}" 2>/dev/null || true)"
  if [ "$status" -ge 200 ] 2>/dev/null && [ "$status" -lt 400 ] 2>/dev/null; then
    record_result "passed" "GET" "$path" "${name} status=${status}"
  else
    record_result "failed" "GET" "$path" "${name} status=${status:-curl_failed}"
  fi
}

test_api() {
  local name="$1"
  local path="$2"
  local file
  file="$(mktemp)"
  tmp_files+=("$file")
  if [ -n "$TOKEN" ]; then
    curl -sS --max-time 20 -H "Authorization: Bearer ${TOKEN}" "${BASE_URL}${path}" >"$file" 2>/dev/null
  else
    curl -sS --max-time 20 "${BASE_URL}${path}" >"$file" 2>/dev/null
  fi
  if json_code_ok "$file"; then
    record_result "passed" "GET" "$path" "$name"
  else
    record_result "failed" "GET" "$path" "$name"
  fi
}

echo "Energy-Maintenance Linux final smoke test"
echo "BaseUrl: ${BASE_URL}"

test_web "static root" "/"
test_web "openapi docs" "/docs"
test_web "openapi json" "/openapi.json"
test_web "spa dashboard fallback" "/dashboard"
test_api "health" "/api/health"
test_api "system status" "/api/system/status"

login_file="$(mktemp)"
tmp_files+=("$login_file")
login_payload="$(python3 - "$USERNAME" "$PASSWORD" <<'PY'
import json
import sys
print(json.dumps({"username": sys.argv[1], "password": sys.argv[2]}))
PY
)"
curl -sS --max-time 20 \
  -H "Content-Type: application/json" \
  -X POST \
  -d "$login_payload" \
  "${BASE_URL}/api/auth/login" >"$login_file" 2>/dev/null

TOKEN="$(extract_token "$login_file" 2>/dev/null || true)"
if [ -n "$TOKEN" ]; then
  record_result "passed" "POST" "/api/auth/login" "token=received"
else
  record_result "failed" "POST" "/api/auth/login" "token=missing"
fi

if [ -n "$TOKEN" ]; then
  test_api "auth me" "/api/auth/me"
  test_api "system statistics" "/api/system/statistics"
  test_api "devices summary" "/api/devices/statistics/summary"
  test_api "devices list" "/api/devices?page=1&page_size=5&device_type=pv_inverter"
  test_api "knowledge documents" "/api/knowledge/documents?page=1&page_size=5"
  test_api "knowledge contributions" "/api/knowledge/contributions?page=1&page_size=5"
  test_api "retrieval records" "/api/retrieval/records?page=1&page_size=5"
  test_api "diagnosis records" "/api/diagnosis/records?page=1&page_size=5"
  test_api "sop templates" "/api/sop/templates?page=1&page_size=5"
  test_api "maintenance tasks" "/api/maintenance/tasks?page=1&page_size=5"
  test_api "record center overview" "/api/record-center/overview"
  test_api "knowledge graph overview" "/api/kg/overview"
  test_api "review knowledge" "/api/review/knowledge?page=1&page_size=5"
  test_api "corrections" "/api/corrections?page=1&page_size=5"
  test_api "model gateway status" "/api/model-gateway/status"
fi

printf '{"status":"%s","base_url":"%s","passed":%s,"failed":%s,"total":%s}\n' \
  "$([ "$FAILED" -eq 0 ] && echo passed || echo failed)" \
  "$BASE_URL" \
  "$PASSED" \
  "$FAILED" \
  "$((PASSED + FAILED))"

[ "$FAILED" -eq 0 ]
