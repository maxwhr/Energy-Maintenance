param(
    [int]$BackendPort = 8000,
    [string]$PostgresRoot = "D:\Work Space\PostgreSQL",
    [Alias("StopPostgreSQL")]
    [switch]$StopPostgres
)

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Status, [string]$Message)
    Write-Output ("[{0}] {1}" -f $Status, $Message)
}

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeDir = Join-Path $RootDir ".runtime"
$pidFile = Join-Path $RuntimeDir "backend.pid"

if (Test-Path -LiteralPath $pidFile) {
    $pidValue = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Write-Step "passed" ("Stopped backend pid={0}" -f $process.Id)
    } else {
        Write-Step "info" ("Backend pid file exists but process is not running: {0}" -f $pidValue)
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Step "info" "No backend pid file found"
}

$portOwner = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($portOwner) {
    Write-Step "warning" ("Port {0} is still listening by pid={1}. Stop it manually if it is an old backend process." -f $BackendPort, $portOwner.OwningProcess)
} else {
    Write-Step "passed" ("Backend port {0} is not listening" -f $BackendPort)
}

if ($StopPostgres) {
    $pgCtl = Join-Path $PostgresRoot "bin\pg_ctl.exe"
    $dataDir = Join-Path $PostgresRoot "data"
    if ((Test-Path -LiteralPath $pgCtl) -and (Test-Path -LiteralPath $dataDir)) {
        & $pgCtl -D $dataDir stop -m fast
        if ($LASTEXITCODE -eq 0) {
            Write-Step "passed" "PostgreSQL standalone process stopped with pg_ctl"
        } else {
            Write-Step "failed" ("pg_ctl stop returned exit code {0}" -f $LASTEXITCODE)
        }
    } else {
        Write-Step "warning" ("Cannot stop PostgreSQL automatically. Checked pg_ctl={0}, data_dir={1}" -f $pgCtl, $dataDir)
    }
} else {
    Write-Step "info" "PostgreSQL was left running. Use -StopPostgres to stop a standalone local instance."
}
