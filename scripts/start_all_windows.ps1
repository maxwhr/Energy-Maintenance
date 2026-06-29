param(
    [int]$BackendPort = 8000,
    [string]$PostgresRoot = "D:\Work Space\PostgreSQL",
    [switch]$SkipPostgreSQL
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Status, [string]$Message)
    Write-Output ("[{0}] {1}" -f $Status, $Message)
}

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RootDir "backend"
$RuntimeDir = Join-Path $RootDir ".runtime"
$LogDir = Join-Path $RuntimeDir "logs"
New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null

Write-Output "Energy-Maintenance Windows startup"
Write-Output ("Project: {0}" -f $RootDir)

if (-not $SkipPostgreSQL) {
    $postgresScript = Join-Path $PSScriptRoot "start_postgresql_standalone.ps1"
    if (Test-Path -LiteralPath $postgresScript) {
        & $postgresScript -PostgresRoot $PostgresRoot
        if ($LASTEXITCODE -ne 0) {
            Write-Step "failed" "PostgreSQL is not reachable."
            Write-Step "info" "Try Administrator repair: scripts/fix_postgresql_service_admin.ps1 -Apply"
            Write-Step "info" "Or temporary standalone startup: scripts/start_postgresql_standalone.ps1"
            throw "PostgreSQL startup helper failed with exit code $LASTEXITCODE"
        }
    } else {
        Write-Step "warning" "scripts/start_postgresql_standalone.ps1 not found; skipping PostgreSQL startup"
    }
}

Push-Location $BackendDir
try {
    Write-Step "info" "Checking Alembic current revision without upgrading"
    uv run python -m alembic -c alembic.ini current
    if ($LASTEXITCODE -ne 0) {
        throw "alembic current failed with exit code $LASTEXITCODE"
    }

    Write-Step "info" "Creating or repairing admin user"
    uv run python .\scripts\create_admin_user.py
    if ($LASTEXITCODE -ne 0) {
        throw "create_admin_user.py failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$portOpen = (Test-NetConnection 127.0.0.1 -Port $BackendPort -WarningAction SilentlyContinue).TcpTestSucceeded
if ($portOpen) {
    Write-Step "passed" ("Backend port {0} is already listening" -f $BackendPort)
} else {
    $backendLog = Join-Path $LogDir "backend.log"
    $command = "cd /d `"$BackendDir`" && uv run uvicorn app.main:app --host 127.0.0.1 --port $BackendPort >> `"$backendLog`" 2>&1"
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", $command) -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath (Join-Path $RuntimeDir "backend.pid") -Value $process.Id -Encoding ASCII
    Start-Sleep -Seconds 5
    $portOpen = (Test-NetConnection 127.0.0.1 -Port $BackendPort -WarningAction SilentlyContinue).TcpTestSucceeded
    if (-not $portOpen) {
        Write-Step "failed" ("Backend did not open port {0}. See {1}" -f $BackendPort, $backendLog)
        exit 1
    }
    Write-Step "passed" ("Backend started on 127.0.0.1:{0}, pid={1}" -f $BackendPort, $process.Id)
}

Write-Step "info" "This script does not execute alembic upgrade head."
Write-Output ("Open: http://127.0.0.1:{0}/" -f $BackendPort)
