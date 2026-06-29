param(
    [string]$PostgresRoot = "D:\Work Space\PostgreSQL",
    [string]$DataDir = ""
)

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Status, [string]$Message)
    Write-Output ("[{0}] {1}" -f $Status, $Message)
}

function Get-PortOwner {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $connection) {
        return $null
    }
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    if (-not $process) {
        return [pscustomobject]@{
            Pid = $connection.OwningProcess
            ProcessName = "unknown"
            Path = ""
        }
    }
    return [pscustomobject]@{
        Pid = $process.Id
        ProcessName = $process.ProcessName
        Path = $process.Path
    }
}

if (-not $DataDir) {
    $DataDir = Join-Path $PostgresRoot "data"
}

Write-Output "Energy-Maintenance standalone PostgreSQL startup helper"
Write-Output "This is a local development fallback and does not modify the Windows service."

$portOpen = (Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($portOpen) {
    $owner = Get-PortOwner -Port 5432
    if ($owner -and $owner.ProcessName -match "postgres|pg_ctl") {
        Write-Step "passed" ("127.0.0.1:5432 is already served by {0} (pid {1})" -f $owner.ProcessName, $owner.Pid)
        exit 0
    }
    $ownerText = if ($owner) { "{0} (pid {1})" -f $owner.ProcessName, $owner.Pid } else { "unknown process" }
    Write-Step "failed" ("127.0.0.1:5432 is occupied by {0}; release the port before starting native PostgreSQL." -f $ownerText)
    exit 2
}

$pgCtl = Join-Path $PostgresRoot "bin\pg_ctl.exe"
if (-not (Test-Path -LiteralPath $pgCtl)) {
    $resolved = Get-Command "pg_ctl.exe" -ErrorAction SilentlyContinue
    if ($resolved) {
        $pgCtl = $resolved.Source
    }
}

if (-not (Test-Path -LiteralPath $pgCtl)) {
    Write-Step "failed" ("pg_ctl.exe not found. Checked {0}" -f $pgCtl)
    exit 1
}
if (-not (Test-Path -LiteralPath $DataDir)) {
    Write-Step "failed" ("PostgreSQL data directory not found: {0}" -f $DataDir)
    exit 1
}

& $pgCtl -D $DataDir start
Start-Sleep -Seconds 5
$portOpen = (Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($portOpen) {
    Write-Step "passed" "PostgreSQL standalone process is running and 5432 is reachable"
    exit 0
}

Write-Step "failed" "pg_ctl start was attempted but 5432 is still unreachable"
exit 1
