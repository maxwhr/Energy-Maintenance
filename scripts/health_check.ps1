$ErrorActionPreference = "Stop"

$baseUrl = "http://127.0.0.1:8000"

Invoke-RestMethod "$baseUrl/api/health"
Invoke-RestMethod "$baseUrl/api/system/status"
