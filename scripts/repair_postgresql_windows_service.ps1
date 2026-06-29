param(
    [string]$ServiceName = "",
    [switch]$Apply
)

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Status, [string]$Message)
    Write-Output ("[{0}] {1}" -f $Status, $Message)
}

if ($ServiceName) {
    $services = @(Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
} else {
    $services = @(Get-Service | Where-Object {
        $_.Name -match "postgres|pgsql" -or $_.DisplayName -match "PostgreSQL|postgres"
    })
}

if (-not $services) {
    Write-Step "failed" "No PostgreSQL Windows service found. Install Windows native PostgreSQL first."
    exit 1
}

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

foreach ($service in $services) {
    $serviceInfo = Get-CimInstance Win32_Service -Filter "Name='$($service.Name)'" -ErrorAction SilentlyContinue
    Write-Step "info" ("{0}: status={1}, startup={2}" -f $service.Name, $service.Status, $serviceInfo.StartMode)
    if (-not $Apply) {
        Write-Step "dry-run" ("Would set startup to Automatic and start service {0} if needed" -f $service.Name)
        continue
    }
    if (-not $isAdmin) {
        Write-Step "failed" "Run PowerShell as Administrator to repair PostgreSQL service startup."
        exit 2
    }
    Set-Service -Name $service.Name -StartupType Automatic
    if ($service.Status -ne "Running") {
        Start-Service -Name $service.Name
        Start-Sleep -Seconds 3
        $service.Refresh()
    }
    Write-Step "passed" ("{0}: status={1}" -f $service.Name, $service.Status)
}
