param(
    [string]$BackendImage = "hybrid-chatbot-api",
    [string]$FrontendImage = "hybrid-chatbot-frontend",
    [switch]$NoCache,
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

function Stop-ProjectStack {
    param(
        [string]$ComposeFilePath,
        [string]$Network
    )

    if (Test-PodmanComposeAvailable) {
        Push-Location $root
        try {
            podman compose -f $ComposeFilePath down --remove-orphans
        } catch {
            Write-Host "Compose shutdown skipped: $($_.Exception.Message)" -ForegroundColor Yellow
        } finally {
            Pop-Location
        }
    }

    Remove-ContainerIfExists "hybrid-chatbot-frontend"
    Remove-ContainerIfExists "hybrid-chatbot-backend"
    Remove-ContainerIfExists "ollama"

    $networkExists = podman network exists $Network
    if ($LASTEXITCODE -eq 0) {
        podman network rm $Network | Out-Null
    }
}

function Remove-ContainerIfExists {
    param([string]$Name)
    $existing = podman ps -a --format "{{.Names}}" | Where-Object { $_ -eq $Name }
    if ($existing) {
        podman rm -f $Name | Out-Null
    }
}

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendEnv = Join-Path $backendDir ".env"
$backendEnvExample = Join-Path $backendDir ".env.example"
$composeFile = Join-Path $root "podman-compose.yml"

Write-Step "Checking existing Podman installation"
podman --version

if (-not (Test-Path $backendEnv)) {
    Copy-Item $backendEnvExample $backendEnv
    Write-Host "Created backend\.env from .env.example" -ForegroundColor Yellow
}

$ollamaModel = "llama3.2:1b"
$ollamaModelLine = Get-Content $backendEnv | Where-Object { $_ -match '^OLLAMA_MODEL=' } | Select-Object -First 1
if ($ollamaModelLine) {
    $ollamaModel = ($ollamaModelLine -replace '^OLLAMA_MODEL=', '').Trim()
}

Write-Step "Stopping existing project containers and network"
Stop-ProjectStack -ComposeFilePath $composeFile -Network $NetworkName

$buildArgs = @("--format", "docker")
if ($NoCache) {
    $buildArgs += "--no-cache"
}

Write-Step "Building backend image"
podman build @buildArgs -t $BackendImage -f (Join-Path $backendDir "Containerfile") $backendDir

Write-Step "Building frontend image"
podman build @buildArgs -t $FrontendImage -f (Join-Path $frontendDir "Containerfile") $frontendDir

Write-Step "Starting stack from images"
if (Test-PodmanComposeAvailable) {
    Push-Location $root
    try {
        podman compose -f $composeFile up -d
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Compose provider not found. Falling back to plain podman run." -ForegroundColor Yellow

    podman network exists $NetworkName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        podman network create $NetworkName | Out-Null
    }

    podman run -d `
      --name ollama `
      --network $NetworkName `
      --network-alias ollama `
      -p 11434:11434 `
      -v ollama_data:/root/.ollama `
      --restart unless-stopped `
      docker.io/ollama/ollama:latest | Out-Null

    podman run -d `
      --name hybrid-chatbot-backend `
      --network $NetworkName `
      --network-alias backend `
      --env-file $backendEnv `
      -e OLLAMA_BASE_URL=http://ollama:11434 `
      -p 8000:8000 `
      --restart unless-stopped `
      --memory 1g `
      --cpus 1 `
      $BackendImage | Out-Null

    podman run -d `
      --name hybrid-chatbot-frontend `
      --network $NetworkName `
      -p 3000:80 `
      --restart unless-stopped `
      --memory 512m `
      --cpus 1 `
      $FrontendImage | Out-Null
}

Write-Step "Waiting for Ollama API"
$deadline = (Get-Date).AddMinutes(3)
$ollamaReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $tags = Invoke-RestMethod -Method Get -Uri "http://localhost:11434/api/tags"
        $ollamaReady = $true
        break
    } catch {
        Start-Sleep -Seconds 3
    }
}
if (-not $ollamaReady) {
    throw "Ollama API did not become ready."
}

Write-Step "Ensuring $ollamaModel model is installed"
$tagNames = @()
if ($tags.models) {
    $tagNames = $tags.models | ForEach-Object { $_.name }
}
if (($tagNames -notcontains $ollamaModel) -and ($tagNames -notcontains "$ollamaModel`:latest")) {
    podman exec ollama ollama pull $ollamaModel
}

Write-Step "Waiting for backend health"
$deadline = (Get-Date).AddMinutes(3)
$backendReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/health"
        if ($health.status -eq "ok") {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}
if (-not $backendReady) {
    throw "Backend did not become healthy."
}

Write-Step "Waiting for frontend"
$deadline = (Get-Date).AddMinutes(2)
$frontendReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        curl.exe -s -S -I http://localhost:3000 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $frontendReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $frontendReady) {
    throw "Frontend did not become ready."
}

Write-Step "Stack is ready"
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "Backend Docs: http://localhost:8000/api/docs" -ForegroundColor Green
Write-Host "Backend ReDoc: http://localhost:8000/api/redoc" -ForegroundColor Green
Write-Host "Frontend Docs Proxy: http://localhost:3000/api/docs" -ForegroundColor Green
Write-Host "Frontend ReDoc Proxy: http://localhost:3000/api/redoc" -ForegroundColor Green
Write-Host "Ollama API: http://localhost:11434/api/tags" -ForegroundColor Green
