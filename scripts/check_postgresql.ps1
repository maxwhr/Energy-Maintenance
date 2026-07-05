param(
    [string]$PostgresRoot = "D:\Work Space\PostgreSQL",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5432,
    [string]$Database = "energy_maintenance",
    [string]$User = "energy_user"
)

$ErrorActionPreference = "Continue"

function Write-Check {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Detail = ""
    )
    if ($Detail) {
        Write-Output ("[{0}] {1}: {2}" -f $Status, $Name, $Detail)
    } else {
        Write-Output ("[{0}] {1}" -f $Status, $Name)
    }
}

$psqlCandidates = @(
    (Join-Path $PostgresRoot "bin\psql.exe"),
    "psql.exe"
)
$pgReadyCandidates = @(
    (Join-Path $PostgresRoot "bin\pg_isready.exe"),
    "pg_isready.exe"
)

$psql = $null
foreach ($candidate in $psqlCandidates) {
    $resolved = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($resolved) {
        $psql = $resolved.Source
        break
    }
}

$pgIsReady = $null
foreach ($candidate in $pgReadyCandidates) {
    $resolved = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($resolved) {
        $pgIsReady = $resolved.Source
        break
    }
}

Write-Output "Energy-Maintenance PostgreSQL check"
Write-Output ("Target: {0}:{1}/{2} as {3}" -f $HostName, $Port, $Database, $User)

if ($psql) {
    Write-Check "psql" "passed" $psql
} else {
    Write-Check "psql" "failed" ("not found; checked {0}\bin\psql.exe and PATH" -f $PostgresRoot)
}

if ($pgIsReady) {
    Write-Check "pg_isready" "passed" $pgIsReady
} else {
    Write-Check "pg_isready" "warning" ("not found; checked {0}\bin\pg_isready.exe and PATH" -f $PostgresRoot)
}

$services = Get-Service | Where-Object {
    $_.Name -match "postgres|pgsql" -or $_.DisplayName -match "PostgreSQL|postgres"
}
if ($services) {
    foreach ($service in $services) {
        $startupType = (Get-CimInstance Win32_Service -Filter "Name='$($service.Name)'" -ErrorAction SilentlyContinue).StartMode
        Write-Check "windows service" "info" ("{0} / {1} / startup={2}" -f $service.Name, $service.Status, $startupType)
        if ($startupType -eq "Disabled") {
            Write-Output ("[action] Use Administrator PowerShell if you want automatic startup: Set-Service -Name {0} -StartupType Automatic" -f $service.Name)
        }
    }
} else {
    Write-Check "windows service" "warning" "no PostgreSQL service found"
}

$portResult = Test-NetConnection $HostName -Port $Port -WarningAction SilentlyContinue
if ($portResult.TcpTestSucceeded) {
    Write-Check "port $Port" "passed" "TCP reachable"
} else {
    Write-Check "port $Port" "failed" "TCP not reachable"
}

if ($pgIsReady) {
    & $pgIsReady -h $HostName -p $Port -d $Database -U $User | Write-Output
    if ($LASTEXITCODE -eq 0) {
        Write-Check "pg_isready target database" "passed"
    } else {
        Write-Check "pg_isready target database" "failed" "exit_code=$LASTEXITCODE"
    }
}

if ($psql) {
    $oldPassword = $env:PGPASSWORD
    if (-not $env:PGPASSWORD) {
        Write-Check "energy_maintenance connection" "skipped" "PGPASSWORD is not set in the current shell"
    } else {
        & $psql -w -h $HostName -p $Port -U $User -d $Database -v ON_ERROR_STOP=1 -c "select current_database(), current_user;" | Write-Output
        if ($LASTEXITCODE -eq 0) {
            Write-Check "energy_maintenance connection" "passed"
        } else {
            Write-Check "energy_maintenance connection" "failed" "exit_code=$LASTEXITCODE"
        }
    }
    $env:PGPASSWORD = $oldPassword
}
