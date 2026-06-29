<#
Example only. This script does not download llama.cpp, install dependencies, or provide a GGUF model.

Prepare llama.cpp and a GGUF model yourself, then adapt the variables below for a local test.
Do not commit real model paths or model files.
#>

param(
    [string]$LlamaServer = "C:\path\to\llama-server.exe",
    [string]$ModelPath = "C:\path\to\model.gguf",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8080
)

Write-Output "Energy-Maintenance llama.cpp example startup"
Write-Output "This is only a template. Edit paths locally before running."

if (-not (Test-Path -LiteralPath $LlamaServer)) {
    Write-Warning "llama-server executable not found. Compile or install llama.cpp first."
    exit 1
}

if (-not (Test-Path -LiteralPath $ModelPath)) {
    Write-Warning "GGUF model file not found. Prepare a local GGUF model first."
    exit 1
}

& $LlamaServer -m $ModelPath --host $HostAddress --port $Port
