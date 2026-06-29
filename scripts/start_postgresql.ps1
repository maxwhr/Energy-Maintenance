param(
    [string]$PostgresRoot = "D:\Work Space\PostgreSQL",
    [string]$DataDir = "",
    [string]$ServiceName = ""
)

$ErrorActionPreference = "Continue"

if (-not $DataDir) {
    $DataDir = Join-Path $PostgresRoot "data"
}

function Write-Step {
    param([string]$Status, [string]$Message)
    Write-Output ("[{0}] {1}" -f $Status, $Message)
}

Write-Output "Energy-Maintenance PostgreSQL native startup helper"
Write-Output "This script does not change Windows service startup type."

$service = $null
if ($ServiceName) {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
} else {
    $service = Get-Service | Where-Object {
        $_.Name -match "postgres|pgsql" -or $_.DisplayName -match "PostgreSQL|postgres"
    } | Select-Object -First 1
}

if ($service) {
    $serviceInfo = Get-CimInstance Win32_Service -Filter "Name='$($service.Name)'" -ErrorAction SilentlyContinue
    Write-Step "info" ("Found service {0}, status={1}, startup={2}" -f $service.Name, $service.Status, $serviceInfo.StartMode)
    if ($serviceInfo.StartMode -eq "Disabled") {
        Write-Step "warning" ("Service is Disabled. Run Administrator PowerShell to enable if desired: Set-Service -Name {0} -StartupType Automatic" -f $service.Name)
        Write-Step "info" "Skipping Start-Service because the service is disabled."
    } elseif ($service.Status -ne "Running") {
        try {
            Start-Service -Name $service.Name -ErrorAction Stop
            Start-Sleep -Seconds 3
            $service.Refresh()
            Write-Step "passed" ("Start-Service requested, current status={0}" -f $service.Status)
        } catch {
            Write-Step "failed" ("Start-Service failed: {0}" -f $_.Exception.Message)
        }
    } else {
        Write-Step "passed" "PostgreSQL service is already running"
    }
} else {
    Write-Step "warning" "No PostgreSQL Windows service found"
}

$pgCtl = Join-Path $PostgresRoot "bin\pg_ctl.exe"
if (-not (Test-Path -LiteralPath $pgCtl)) {
    $resolvedPgCtl = Get-Command "pg_ctl.exe" -ErrorAction SilentlyContinue
    if ($resolvedPgCtl) {
        $pgCtl = $resolvedPgCtl.Source
    }
}

$portOpen = (Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($portOpen) {
    Write-Step "passed" "127.0.0.1:5432 is reachable"
    exit 0
}

if ((Test-Path -LiteralPath $pgCtl) -and (Test-Path -LiteralPath $DataDir)) {
    Write-Step "info" ("Trying pg_ctl with data dir: {0}" -f $DataDir)
    & $pgCtl -D $DataDir start
    Start-Sleep -Seconds 5
    $portOpen = (Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
    if ($portOpen) {
        Write-Step "passed" "PostgreSQL started and 127.0.0.1:5432 is reachable"
        exit 0
    }
    Write-Step "failed" "pg_ctl was invoked but port 5432 is still not reachable"
    exit 1
}

Write-Step "failed" ("Cannot start PostgreSQL automatically. Checked pg_ctl={0}, data_dir={1}" -f $pgCtl, $DataDir)
Write-Output "Install or start Windows native PostgreSQL, then run scripts/check_postgresql.ps1."
exit 1
