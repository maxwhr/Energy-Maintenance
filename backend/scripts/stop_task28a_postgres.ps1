Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runtimeRoot = Join-Path $projectRoot '.runtime\task28a\postgres'
$dataDirectory = Join-Path $runtimeRoot 'data'
$binPathFile = Join-Path $runtimeRoot 'runtime\bin_path.txt'
$port = 55433

if (-not (Test-Path -LiteralPath (Join-Path $dataDirectory 'PG_VERSION'))) {
    throw 'Task 28A project-local PostgreSQL data directory is not initialized.'
}
if (-not (Test-Path -LiteralPath $binPathFile)) {
    throw 'Task 28A PostgreSQL bin configuration is missing.'
}

$binDirectory = (Get-Content -LiteralPath $binPathFile -Raw -Encoding UTF8).Trim()
$pgCtl = Join-Path $binDirectory 'pg_ctl.exe'
$pgIsReady = Join-Path $binDirectory 'pg_isready.exe'
foreach ($tool in @($pgCtl, $pgIsReady)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        throw "Task 28A PostgreSQL tool is missing: $tool"
    }
}

& $pgCtl -D $dataDirectory status | Out-Null
if ($LASTEXITCODE -ne 0) {
    [pscustomobject]@{ status = 'already_stopped'; data_directory = $dataDirectory; port = $port } | ConvertTo-Json -Compress
    exit 0
}

& $pgCtl -D $dataDirectory stop -m fast | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Task 28A PostgreSQL cluster failed to stop.'
}
& $pgIsReady -h 127.0.0.1 -p $port | Out-Null
if ($LASTEXITCODE -eq 0) {
    throw 'Port 55433 still accepts PostgreSQL connections after the Task 28A stop command.'
}

[pscustomobject]@{ status = 'stopped'; data_directory = $dataDirectory; port = $port } | ConvertTo-Json -Compress
