Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runtimeRoot = Join-Path $projectRoot '.runtime\task28a\postgres'
$dataDirectory = Join-Path $runtimeRoot 'data'
$logDirectory = Join-Path $runtimeRoot 'logs'
$logPath = Join-Path $logDirectory 'postgres.log'
$binPathFile = Join-Path $runtimeRoot 'runtime\bin_path.txt'
$port = 55433

if (-not (Test-Path -LiteralPath (Join-Path $dataDirectory 'PG_VERSION'))) {
    throw 'Task 28A project-local PostgreSQL data directory is not initialized.'
}
if (-not (Test-Path -LiteralPath $binPathFile)) {
    throw 'Task 28A PostgreSQL bin configuration is missing.'
}

$binDirectory = (Get-Content -LiteralPath $binPathFile -Raw -Encoding UTF8).Trim()
$requiredTools = @('pg_ctl.exe', 'pg_isready.exe', 'postgres.exe')
foreach ($tool in $requiredTools) {
    if (-not (Test-Path -LiteralPath (Join-Path $binDirectory $tool))) {
        throw "Task 28A PostgreSQL tool is missing: $tool"
    }
}

$pgCtl = Join-Path $binDirectory 'pg_ctl.exe'
$pgIsReady = Join-Path $binDirectory 'pg_isready.exe'
$statusOutput = & $pgCtl -D $dataDirectory status 2>&1
if ($LASTEXITCODE -eq 0) {
    [pscustomobject]@{ status = 'already_running'; data_directory = $dataDirectory; port = $port } | ConvertTo-Json -Compress
    exit 0
}

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $port is already in use by a process that is not this Task 28A cluster."
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
& $pgCtl -D $dataDirectory -l $logPath -o "-h 127.0.0.1 -p $port" start | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Task 28A PostgreSQL cluster failed to start. Inspect only the project-local log file.'
}

for ($attempt = 1; $attempt -le 30; $attempt++) {
    & $pgIsReady -h 127.0.0.1 -p $port | Out-Null
    if ($LASTEXITCODE -eq 0) {
        [pscustomobject]@{ status = 'running'; data_directory = $dataDirectory; port = $port; attempts = $attempt } | ConvertTo-Json -Compress
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw 'Task 28A PostgreSQL cluster did not become ready within 15 seconds.'
