param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "admin",
    [string]$Password = $env:FULL_SMOKE_ADMIN_PASSWORD,
    [switch]$IncludeRetrievalQuery
)

$ErrorActionPreference = "Stop"
$results = New-Object System.Collections.Generic.List[object]

if ([string]::IsNullOrWhiteSpace($Password)) {
    Write-Warning "FULL_SMOKE_ADMIN_PASSWORD is not set. Using the local-development password fallback; do not use this fallback for production acceptance."
    $Password = "admin123456"
}

function Add-Result {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Path,
        [bool]$Passed,
        [string]$Notes = ""
    )
    $results.Add([pscustomobject]@{
        name = $Name
        method = $Method
        path = $Path
        passed = $Passed
        notes = $Notes
    }) | Out-Null
    $status = if ($Passed) { "passed" } else { "failed" }
    Write-Output ("[{0}] {1} {2} {3} {4}" -f $status, $Method, $Path, $Name, $Notes)
}

function Test-Web {
    param([string]$Name, [string]$Path)
    try {
        $response = Invoke-WebRequest -Method GET -Uri ($BaseUrl + $Path) -UseBasicParsing -TimeoutSec 20
        Add-Result $Name "GET" $Path ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) ("status={0}" -f $response.StatusCode)
    } catch {
        Add-Result $Name "GET" $Path $false $_.Exception.Message
    }
}

function Test-Api {
    param(
        [string]$Name,
        [string]$Path,
        [string]$Token = ""
    )
    try {
        $headers = @{}
        if ($Token) {
            $headers.Authorization = "Bearer $Token"
        }
        $response = Invoke-RestMethod -Method GET -Uri ($BaseUrl + $Path) -Headers $headers -TimeoutSec 20
        $ok = ($null -ne $response) -and ($response.code -eq 0 -or $response.code -eq 200)
        Add-Result $Name "GET" $Path $ok ("code={0}" -f $response.code)
        return $response
    } catch {
        Add-Result $Name "GET" $Path $false $_.Exception.Message
        return $null
    }
}

Write-Output "Energy-Maintenance final smoke test"
Write-Output ("BaseUrl: {0}" -f $BaseUrl)

Test-Web "static root" "/"
Test-Web "openapi docs" "/docs"
Test-Web "openapi json" "/openapi.json"
Test-Web "spa dashboard fallback" "/dashboard"
Test-Api "health" "/api/health" | Out-Null
Test-Api "system status" "/api/system/status" | Out-Null

$token = ""
try {
    $loginPayload = @{ username = $Username; password = $Password } | ConvertTo-Json -Compress
    $login = Invoke-RestMethod -Method POST -Uri ($BaseUrl + "/api/auth/login") -ContentType "application/json" -Body $loginPayload -TimeoutSec 20
    $token = [string]$login.data.access_token
    Add-Result "admin login" "POST" "/api/auth/login" ([bool]$token) "token=received"
} catch {
    Add-Result "admin login" "POST" "/api/auth/login" $false $_.Exception.Message
}

if ($token) {
    Test-Api "auth me" "/api/auth/me" $token | Out-Null
    Test-Api "system statistics" "/api/system/statistics" $token | Out-Null
    Test-Api "devices summary" "/api/devices/statistics/summary" $token | Out-Null
    Test-Api "devices list" "/api/devices?page=1&page_size=5&device_type=pv_inverter" $token | Out-Null
    Test-Api "knowledge documents" "/api/knowledge/documents?page=1&page_size=5" $token | Out-Null
    Test-Api "knowledge contributions" "/api/knowledge/contributions?page=1&page_size=5" $token | Out-Null
    if ($IncludeRetrievalQuery) {
        try {
            $retrievalPayload = @{
                query = "Task16 verification PV inverter alarm troubleshooting"
                manufacturer = "huawei"
                product_series = "SUN2000"
                device_type = "pv_inverter"
                top_k = 3
                enable_model_enhancement = $false
            } | ConvertTo-Json -Compress
            $headers = @{ Authorization = "Bearer $token" }
            $retrieval = Invoke-RestMethod -Method POST -Uri ($BaseUrl + "/api/retrieval/query") -Headers $headers -ContentType "application/json" -Body $retrievalPayload -TimeoutSec 30
            Add-Result "retrieval query" "POST" "/api/retrieval/query" ($retrieval.code -eq 0 -or $retrieval.code -eq 200) ("trace_id={0}" -f $retrieval.data.trace_id)
        } catch {
            Add-Result "retrieval query" "POST" "/api/retrieval/query" $false $_.Exception.Message
        }
    } else {
        Add-Result "retrieval query" "POST" "/api/retrieval/query" $true "skipped by default to avoid creating qa_records; rerun with -IncludeRetrievalQuery"
    }
    Test-Api "retrieval records" "/api/retrieval/records?page=1&page_size=5" $token | Out-Null
    Test-Api "diagnosis records" "/api/diagnosis/records?page=1&page_size=5" $token | Out-Null
    Test-Api "sop templates" "/api/sop/templates?page=1&page_size=5" $token | Out-Null
    Test-Api "maintenance tasks" "/api/maintenance/tasks?page=1&page_size=5" $token | Out-Null
    Test-Api "record center overview" "/api/record-center/overview" $token | Out-Null
    Test-Api "knowledge graph overview" "/api/kg/overview" $token | Out-Null
    Test-Api "review knowledge" "/api/review/knowledge?page=1&page_size=5" $token | Out-Null
    Test-Api "corrections" "/api/corrections?page=1&page_size=5" $token | Out-Null
    Test-Api "model gateway status" "/api/model-gateway/status" $token | Out-Null
}

$failed = @($results | Where-Object { -not $_.passed })
$summary = [pscustomobject]@{
    status = if ($failed.Count -eq 0) { "passed" } else { "failed" }
    base_url = $BaseUrl
    total = $results.Count
    failed = $failed.Count
    results = $results
}
$summary | ConvertTo-Json -Depth 6

if ($failed.Count -gt 0) {
    exit 1
}
exit 0
