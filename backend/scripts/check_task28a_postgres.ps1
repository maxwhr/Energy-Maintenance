Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runtimeRoot = Join-Path $projectRoot '.runtime\task28a\postgres'
$dataDirectory = Join-Path $runtimeRoot 'data'
$binPathFile = Join-Path $runtimeRoot 'runtime\bin_path.txt'
$port = 55433

if (-not (Test-Path -LiteralPath (Join-Path $dataDirectory 'PG_VERSION'))) {
    [pscustomobject]@{ status = 'not_initialized'; data_directory = $dataDirectory; port = $port } | ConvertTo-Json -Compress
    exit 1
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
$clusterRunning = $LASTEXITCODE -eq 0
& $pgIsReady -h 127.0.0.1 -p $port | Out-Null
$portReady = $LASTEXITCODE -eq 0
[pscustomobject]@{
    status = if ($clusterRunning -and $portReady) { 'running' } elseif (-not $clusterRunning -and -not $portReady) { 'stopped' } else { 'inconsistent' }
    data_directory = $dataDirectory
    port = $port
    cluster_running = $clusterRunning
    port_ready = $portReady
} | ConvertTo-Json -Compress
if ($clusterRunning -and $portReady) { exit 0 }
exit 1
