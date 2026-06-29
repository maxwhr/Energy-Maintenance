param(
    [string]$PostgresRoot = "D:\Work Space\PostgreSQL"
)

$ErrorActionPreference = "Continue"

function Write-Check {
    param([string]$Name, [string]$Status, [string]$Detail = "")
    if ($Detail) {
        Write-Output ("[{0}] {1}: {2}" -f $Status, $Name, $Detail)
    } else {
        Write-Output ("[{0}] {1}" -f $Status, $Name)
    }
}

Write-Output "Energy-Maintenance Windows environment check"
Write-Check "PowerShell" "info" $PSVersionTable.PSVersion.ToString()
Write-Check "Project" "info" (Resolve-Path (Join-Path $PSScriptRoot ".."))

foreach ($command in @("python.exe", "uv.exe", "node.exe", "npm.cmd")) {
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    if ($resolved) {
        Write-Check $command "passed" $resolved.Source
    } else {
        Write-Check $command "warning" "not found in PATH"
    }
}

$psql = Get-Command (Join-Path $PostgresRoot "bin\psql.exe") -ErrorAction SilentlyContinue
if (-not $psql) {
    $psql = Get-Command "psql.exe" -ErrorAction SilentlyContinue
}
if ($psql) {
    Write-Check "psql" "passed" $psql.Source
} else {
    Write-Check "psql" "warning" "not found"
}

$service = Get-Service | Where-Object {
    $_.Name -match "postgres|pgsql" -or $_.DisplayName -match "PostgreSQL|postgres"
} | Select-Object -First 1
if ($service) {
    $startup = (Get-CimInstance Win32_Service -Filter "Name='$($service.Name)'" -ErrorAction SilentlyContinue).StartMode
    Write-Check "PostgreSQL service" "info" ("{0}, status={1}, startup={2}" -f $service.Name, $service.Status, $startup)
} else {
    Write-Check "PostgreSQL service" "warning" "not found"
}

$portOpen = (Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
Write-Check "127.0.0.1:5432" ($(if ($portOpen) { "passed" } else { "failed" })) ($(if ($portOpen) { "reachable" } else { "not reachable" }))
Write-Output "Docker is not required and is not the formal deployment route."
