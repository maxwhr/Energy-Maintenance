param(
    [string]$Command = "tesseract",
    [string[]]$RequiredLanguages = @("chi_sim", "eng")
)

$ErrorActionPreference = "Continue"
$result = [ordered]@{
    command = $Command
    found = $false
    version = $null
    tessdata_visible = $false
    required_languages = $RequiredLanguages
    missing_languages = @()
    status = "not_configured"
    notes = @()
}

Write-Output "Energy-Maintenance optional Tesseract OCR environment check"
Write-Output "This script only checks the local environment. It does not install Tesseract or language packages."

$resolved = Get-Command $Command -ErrorAction SilentlyContinue
if (-not $resolved) {
    $result.notes += "tesseract command was not found in PATH"
    $result.missing_languages = $RequiredLanguages
    $result | ConvertTo-Json -Depth 5
    exit 0
}

$result.found = $true
$result.notes += ("command_path={0}" -f $resolved.Source)

try {
    $versionOutput = & $Command --version 2>&1
    $result.version = ($versionOutput | Select-Object -First 1)
    Write-Output ("[passed] version: {0}" -f $result.version)
} catch {
    $result.notes += ("version check failed: {0}" -f $_.Exception.Message)
}

try {
    $langsOutput = & $Command --list-langs 2>&1
    $langs = @($langsOutput | Where-Object { $_ -and ($_ -notmatch "^List of") } | ForEach-Object { $_.Trim() })
    $result.tessdata_visible = $langs.Count -gt 0
    $missing = @()
    foreach ($lang in $RequiredLanguages) {
        if ($langs -notcontains $lang) {
            $missing += $lang
        }
    }
    $result.missing_languages = $missing
    if ($missing.Count -eq 0) {
        $result.status = "available"
        Write-Output "[passed] required languages are visible"
    } else {
        $result.status = "not_configured"
        Write-Output ("[blocked] missing languages: {0}" -f ($missing -join ", "))
    }
} catch {
    $result.notes += ("language check failed: {0}" -f $_.Exception.Message)
}

$result | ConvertTo-Json -Depth 5
exit 0
