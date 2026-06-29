param(
    [string]$ServiceName = "postgresql-x64-16",
    [switch]$Apply
)

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Status, [string]$Message)
    Write-Output ("[{0}] {1}" -f $Status, $Message)
}

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    $service = Get-Service | Where-Object {
        $_.Name -match "postgres|pgsql" -or $_.DisplayName -match "PostgreSQL|postgres"
    } | Select-Object -First 1
}

if (-not $service) {
    Write-Step "failed" "No PostgreSQL Windows service found. Install Windows native PostgreSQL first."
    exit 1
}

$serviceInfo = Get-CimInstance Win32_Service -Filter "Name='$($service.Name)'" -ErrorAction SilentlyContinue
Write-Step "info" ("Service={0}, status={1}, startup={2}" -f $service.Name, $service.Status, $serviceInfo.StartMode)

if (-not $Apply) {
    Write-Step "dry-run" ("Would run: Set-Service -Name {0} -StartupType Automatic; Start-Service -Name {0}" -f $service.Name)
    Write-Step "info" "Rerun as Administrator with -Apply to repair service startup."
    exit 0
}

if (-not $isAdmin) {
    Write-Step "failed" "This script must be run from Administrator PowerShell when -Apply is used."
    exit 2
}

Set-Service -Name $service.Name -StartupType Automatic
Start-Service -Name $service.Name -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
$service.Refresh()
$portOpen = (Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($service.Status -eq "Running" -and $portOpen) {
    Write-Step "passed" ("{0} is running and 5432 is reachable" -f $service.Name)
    exit 0
}

Write-Step "failed" ("Service status={0}, port5432={1}" -f $service.Status, $portOpen)
exit 1
