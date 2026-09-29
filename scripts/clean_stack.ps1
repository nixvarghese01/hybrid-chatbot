param(
    [string]$NetworkName = "hybrid-chatbot-net",
    [switch]$RemoveImages,
    [switch]$PruneDanglingImages,
    [switch]$RemoveOllamaVolume
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$stopScript = Join-Path $PSScriptRoot "stop_stack.ps1"

Write-Step "Stopping project stack before cleanup"
powershell -ExecutionPolicy Bypass -File $stopScript -NetworkName $NetworkName

Write-Step "Cleaning project resources"

$ollamaVolumeExists = podman volume ls --format "{{.Name}}" | Where-Object { $_ -eq "ollama_data" }
if ($ollamaVolumeExists -and -not $RemoveOllamaVolume) {
    Write-Host "Preserving ollama_data volume by default." -ForegroundColor Yellow
}

if ($RemoveImages) {
    $projectImages = @(
        "localhost/hybrid-chatbot-api:latest",
        "localhost/hybrid-chatbot-frontend:latest"
    )

    foreach ($image in $projectImages) {
        try {
            podman image rm $image | Out-Null
            Write-Host "Removed image $image" -ForegroundColor Yellow
        } catch {
            Write-Host ("Skipped image {0}: {1}" -f $image, $_.Exception.Message) -ForegroundColor Yellow
        }
    }
}

if ($RemoveOllamaVolume -and $ollamaVolumeExists) {
    podman volume rm ollama_data | Out-Null
    Write-Host "Removed ollama_data volume" -ForegroundColor Yellow
}

if ($PruneDanglingImages) {
    podman image prune -f | Out-Null
    Write-Host "Pruned dangling images" -ForegroundColor Yellow
}

Write-Step "Cleanup complete"
