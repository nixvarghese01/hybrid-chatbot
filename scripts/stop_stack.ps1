param(
    [string]$NetworkName = "hybrid-chatbot-net"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-PodmanComposeAvailable {
    $podmanCompose = Get-Command podman-compose -ErrorAction SilentlyContinue
    $dockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
    return ($null -ne $podmanCompose) -or ($null -ne $dockerCompose)
}

function Remove-ContainerIfExists {
    param([string]$Name)
    $existing = podman ps -a --format "{{.Names}}" | Where-Object { $_ -eq $Name }
    if ($existing) {
        podman rm -f $Name | Out-Null
        Write-Host "Removed $Name" -ForegroundColor Yellow
    }
}

$root = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $root "podman-compose.yml"

Write-Step "Checking existing Podman installation"
podman --version | Out-Null

Write-Step "Stopping project stack"
if (Test-PodmanComposeAvailable) {
    Push-Location $root
    try {
        podman compose -f $composeFile down --remove-orphans
    } catch {
        Write-Host "Compose shutdown skipped: $($_.Exception.Message)" -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
}

Remove-ContainerIfExists "hybrid-chatbot-frontend"
Remove-ContainerIfExists "hybrid-chatbot-backend"
Remove-ContainerIfExists "ollama"

podman network exists $NetworkName | Out-Null
if ($LASTEXITCODE -eq 0) {
    podman network rm $NetworkName | Out-Null
    Write-Host "Removed network $NetworkName" -ForegroundColor Yellow
}

Write-Step "Stack stopped"
