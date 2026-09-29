$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

Write-Step "Podman version"
podman --version

Write-Step "Project containers"
podman ps -a --filter "name=hybrid-chatbot-frontend" --filter "name=hybrid-chatbot-backend" --filter "name=ollama"

Write-Step "Project endpoints"
try {
    $health = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/health"
    Write-Host "Backend health: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "Backend health: unavailable" -ForegroundColor Yellow
}

foreach ($endpoint in @(
    @{ Name = "Frontend"; Url = "http://localhost:3000" },
    @{ Name = "Swagger"; Url = "http://localhost:3000/api/docs" },
    @{ Name = "ReDoc"; Url = "http://localhost:3000/api/redoc" },
    @{ Name = "Ollama"; Url = "http://localhost:11434/api/tags" }
)) {
    try {
        $response = Invoke-WebRequest -Uri $endpoint.Url -Method Get -UseBasicParsing
        $statusCode = [int]$response.StatusCode
        Write-Host "$($endpoint.Name): $statusCode" -ForegroundColor Green
    } catch {
        Write-Host "$($endpoint.Name): unavailable" -ForegroundColor Yellow
    }
}
