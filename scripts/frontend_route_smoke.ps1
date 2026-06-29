param(
    [string]$FrontendDir = "D:\Work Space\Energy-Maintenance\frontend",
    [string]$BaseUrl = "http://127.0.0.1:5173",
    [int]$Port = 5173
)

$ErrorActionPreference = "Continue"

$routes = @(
    "/login",
    "/dashboard",
    "/status",
    "/devices",
    "/knowledge",
    "/retrieval",
    "/diagnosis",
    "/sop",
    "/tasks",
    "/records",
    "/review",
    "/model-service"
)

function Test-AppShell {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
        $content = [string]$response.Content
        return ($response.StatusCode -eq 200 -and ($content -match 'id="app"' -or $content -match "/src/main.ts" -or $content -match "/assets/"))
    } catch {
        return $false
    }
}

$startedProcess = $null
$serverRunning = (Test-NetConnection 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded

if (-not $serverRunning) {
    if (-not (Test-Path -LiteralPath $FrontendDir)) {
        Write-Output ("[failed] frontend directory not found: {0}" -f $FrontendDir)
        exit 1
    }
    Write-Output "[info] Vite dev server is not running; starting a temporary server."
    $startedProcess = Start-Process -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $FrontendDir `
        -WindowStyle Hidden `
        -PassThru

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((Test-NetConnection 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        Write-Output "[failed] Vite dev server did not become ready."
        if ($startedProcess) {
            Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
        }
        exit 1
    }
} else {
    Write-Output "[info] Reusing existing Vite server."
}

$failed = @()
foreach ($route in $routes) {
    $url = $BaseUrl.TrimEnd("/") + $route
    if (Test-AppShell $url) {
        Write-Output ("[passed] {0}" -f $route)
    } else {
        Write-Output ("[failed] {0}" -f $route)
        $failed += $route
    }
}

if ($startedProcess) {
    Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
    $nodeProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match "vite" -and $_.CommandLine -match "127.0.0.1" -and $_.CommandLine -match "$Port"
    }
    foreach ($nodeProcess in $nodeProcesses) {
        Stop-Process -Id $nodeProcess.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

if ($failed.Count -gt 0) {
    Write-Output ("[summary] failed routes: {0}" -f ($failed -join ", "))
    exit 1
}

Write-Output "[summary] all frontend routes returned the app shell."
exit 0
