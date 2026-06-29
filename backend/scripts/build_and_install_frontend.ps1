$ErrorActionPreference = "Stop"

$BackendDir = (Resolve-Path "$PSScriptRoot\..").Path
$ProjectRoot = (Resolve-Path (Join-Path $BackendDir "..")).Path
$defaultFrontendSourceDir = Join-Path $ProjectRoot "frontend"
$FrontendSourceDir = if ($env:FRONTEND_SOURCE_DIR) { $env:FRONTEND_SOURCE_DIR } else { $defaultFrontendSourceDir }

$distDir = Join-Path $FrontendSourceDir "dist"
$staticRoot = Join-Path $BackendDir "static"
$targetDir = Join-Path $staticRoot "frontend"

if (!(Test-Path $FrontendSourceDir)) {
    throw "Frontend source directory does not exist: $FrontendSourceDir"
}

Push-Location $FrontendSourceDir
try {
    npm.cmd install
    npm.cmd run build
}
finally {
    Pop-Location
}

if (!(Test-Path (Join-Path $distDir "index.html"))) {
    throw "Frontend build output is missing index.html: $distDir"
}

if (!(Test-Path $staticRoot)) {
    New-Item -ItemType Directory -Path $staticRoot | Out-Null
}

$staticRootResolved = (Resolve-Path $staticRoot).Path
if (Test-Path $targetDir) {
    $targetResolved = (Resolve-Path $targetDir).Path
    if (!$targetResolved.StartsWith($staticRootResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe target directory: $targetResolved"
    }
    Remove-Item -LiteralPath $targetResolved -Recurse -Force
}

New-Item -ItemType Directory -Path $targetDir | Out-Null
Copy-Item -Path (Join-Path $distDir "*") -Destination $targetDir -Recurse -Force

$fileCount = (Get-ChildItem -Path $targetDir -Recurse -File | Measure-Object).Count
Write-Host "Frontend installed to: $targetDir"
Write-Host "Copied files: $fileCount"
Write-Host "Index: $(Join-Path $targetDir 'index.html')"
