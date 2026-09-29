param(
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "container_stack.ps1"
$args = @()

if ($NoCache) {
    $args += "-NoCache"
}

powershell -ExecutionPolicy Bypass -File $scriptPath @args
