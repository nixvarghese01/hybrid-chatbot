# Hybrid Chatbot Application

Hybrid chatbot platform with a React frontend, a FastAPI backend, OpenAI and Gemini for cloud reasoning, and Ollama for local or self-hosted inference. This repository is now Podman-only for build, runtime, and verification workflows.

## Aim

The aim of this project is to provide a clean production-style chatbot foundation that can:

- expose a single chat API
- switch between cloud and local AI models
- keep privacy-sensitive prompts on the local model
- fall back gracefully if the cloud model fails
- run fully in containers with Podman

## Why This Architecture

We use a hybrid AI setup because one model path is not ideal for every request:

- OpenAI and Gemini provide cloud model paths for stronger reasoning and faster hosted responses.
- Ollama is the safer local path for private prompts, lower cloud dependency, and resilience.
- The router allows the app to choose the best path automatically while still supporting an explicit `use_local` override.

## Chatbot Purpose

This project is a starter template for:

- internal assistants
- support copilots
- privacy-aware local AI workflows
- hybrid cloud plus local experimentation
- containerized deployments in Podman environments

## Stack

### Frontend

- React
  Purpose: chat UI with message history, model selector, and loading state
- Vite
  Purpose: static asset build for the frontend container
- Nginx
  Purpose: serves the built frontend and proxies `/api` requests to the backend container

### Backend

- FastAPI
  Purpose: async API with typed request and response models
- Uvicorn
  Purpose: ASGI server for the FastAPI app
- Pydantic
  Purpose: request validation and predictable schema handling

### AI Integrations

- OpenAI
  Purpose: cloud model path for complex reasoning
- Gemini
  Purpose: additional cloud model path with fast hosted inference and free-tier-friendly usage
- Ollama
  Purpose: local model path for privacy-sensitive or self-hosted requests

### Container Platform

- Podman
  Purpose: image build and container runtime
- `podman compose`
  Purpose: multi-container orchestration when a compose provider is installed
- Podman network fallback
  Purpose: keeps the stack fully runnable even when `podman compose` is unavailable on the machine

Important:

- local scripts assume Podman is already installed
- this repo does not install Podman on your local machine
- container build and run are done with Podman only

## Project Structure

```text
.
|-- .github/
|-- backend/
|   |-- services/
|   |   |-- gemini_client.py
|   |   |-- ollama_client.py
|   |   |-- openai_client.py
|   |   `-- router.py
|   |-- tests/
|   |   `-- test_main.py
|   |-- .dockerignore
|   |-- .env.example
|   |-- Containerfile
|   |-- main.py
|   `-- requirements.txt
|-- frontend/
|   |-- nginx/
|   |   `-- default.conf
|   |-- public/
|   |-- src/
|   |   |-- App.jsx
|   |   |-- main.jsx
|   |   `-- styles.css
|   |-- .dockerignore
|   |-- .env.example
|   |-- Containerfile
|   |-- index.html
|   |-- package-lock.json
|   `-- package.json
|-- scripts/
|   |-- clean_stack.ps1
|   |-- container_stack.ps1
|   |-- start_stack.ps1
|   |-- status_stack.ps1
|   `-- stop_stack.ps1
|-- .dockerignore
|-- .gitignore
|-- podman-compose.yml
`-- README.md
```

## Runtime Behavior

### Backend Endpoints

- `GET /health`
- `POST /chat`
- `GET /api/docs`
- `GET /api/redoc`
- `GET /api/openapi.json`

### Routing Rules

- `use_local=true` routes directly to Ollama
- `cloud_provider=openai` forces the OpenAI cloud route
- `cloud_provider=gemini` forces the Gemini cloud route
- sensitive keywords route to Ollama
- complex reasoning requests prefer the configured cloud provider
- if the configured cloud provider fails, the router tries the alternate cloud provider if configured
- if cloud providers fail, the backend falls back to Ollama

### Operational Behavior

- OpenAI client has retry and timeout handling
- Gemini client has retry and timeout handling
- Ollama client has retry and timeout handling
- router logs the chosen model provider
- CORS is enabled for frontend access
- the frontend exposes direct route choices for `Local`, `OpenAI`, and `Gemini`

## Environment Configuration

Create the backend environment file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Backend variables:

```env
CLOUD_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_OUTPUT_TOKENS=256

# Host Ollama
OLLAMA_BASE_URL=http://host.containers.internal:11434

# Containerized Ollama
# OLLAMA_BASE_URL=http://ollama:11434

OLLAMA_MODEL=llama3.2:1b
OLLAMA_NUM_PREDICT=192
REQUEST_TIMEOUT_SECONDS=60
MODEL_RETRY_COUNT=2
MODEL_RETRY_DELAY_SECONDS=1
ROUTER_TIMEOUT_SECONDS=75
ROUTER_RETRY_COUNT=1
ROUTER_RETRY_DELAY_SECONDS=1
```

Notes:

- For the containerized stack in this repo, `container_stack.ps1` forces `OLLAMA_BASE_URL=http://ollama:11434` for the backend container.
- The frontend container uses `/api` and does not require a local frontend build step.
- Set `CLOUD_PROVIDER=openai` to prefer OpenAI first, or `CLOUD_PROVIDER=gemini` to prefer Gemini first.
- The frontend can override the default cloud provider per request, so users can pick `OpenAI` or `Gemini` directly in the UI.

## Podman Deployment

This project is meant to be built and run with Podman images only.

### Standard Start

```powershell
.\scripts\container_stack.ps1
```

What the script does:

- checks the existing Podman installation
- stops old project containers and removes the project network
- builds the backend multi-stage image
- builds the frontend multi-stage image
- starts the stack with `podman compose` if a compose provider exists
- otherwise starts the same stack with plain `podman run`
- waits for Ollama to become ready
- pulls the configured Ollama model if it is missing
- verifies backend health
- verifies frontend availability

### Easy Local Management

Use these helper scripts for day-to-day work:

```powershell
.\scripts\start_stack.ps1
.\scripts\stop_stack.ps1
.\scripts\status_stack.ps1
.\scripts\clean_stack.ps1
```

What each one does:

- `start_stack.ps1`
  Builds current images and starts the full stack
- `stop_stack.ps1`
  Stops project containers and removes the project network
- `status_stack.ps1`
  Shows container status plus frontend, docs, redoc, and Ollama endpoint health
- `clean_stack.ps1`
  Stops the stack and removes runtime resources while preserving the Ollama model volume by default

Useful cleanup options:

```powershell
.\scripts\clean_stack.ps1 -RemoveImages
.\scripts\clean_stack.ps1 -PruneDanglingImages
.\scripts\clean_stack.ps1 -RemoveOllamaVolume
```

Notes:

- `-RemoveImages` removes only the project runtime images
- `-PruneDanglingImages` removes dangling Podman build layers
- `-RemoveOllamaVolume` deletes the stored Ollama models and forces model re-download next start

### Published URLs

- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/api/docs`
- backend redoc: `http://localhost:8000/api/redoc`
- proxied docs from frontend: `http://localhost:3000/api/docs`
- proxied redoc from frontend: `http://localhost:3000/api/redoc`
- backend health: `http://localhost:8000/health`
- ollama tags: `http://localhost:11434/api/tags`

Expected local response time:

- with `llama3.2:1b`, short local replies are usually within about `8` to `30` seconds on this laptop-class setup
- first requests after a restart can be slower while the model warms up

### Logs

If `podman compose` is available:

```powershell
podman compose -f podman-compose.yml logs -f frontend
podman compose -f podman-compose.yml logs -f backend
podman compose -f podman-compose.yml logs -f ollama
```

If the stack is started through the fallback path:

```powershell
podman logs -f hybrid-chatbot-frontend
podman logs -f hybrid-chatbot-backend
podman logs -f ollama
```

### Stop The Stack

```powershell
podman rm -f hybrid-chatbot-frontend hybrid-chatbot-backend ollama
podman network rm hybrid-chatbot-net
```

## Build And Verification

### Build Images With Podman

```powershell
podman build --format docker -t hybrid-chatbot-api -f backend\Containerfile backend
podman build --format docker -t hybrid-chatbot-frontend -f frontend\Containerfile frontend
```

### Run Backend Smoke Tests In Container

```powershell
podman build --format docker -t hybrid-chatbot-api-test -f backend\Containerfile backend
podman run --rm --workdir /app -v ${PWD}\backend\tests:/app/tests:Z hybrid-chatbot-api-test pytest -q tests/test_main.py
```

### Verify Running Services

```powershell
curl.exe -I http://localhost:3000
curl.exe http://localhost:8000/health
curl.exe http://localhost:11434/api/tags
curl.exe -I http://localhost:3000/api/docs
curl.exe -I http://localhost:3000/api/redoc
```

### Verify End-To-End Chat

```powershell
$body = @{ message = "Say hello in one sentence."; use_local = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:3000/api/chat" -ContentType "application/json" -Body $body
```

Verify a specific cloud route:

```powershell
$body = @{ message = "Reply with exactly: cloud-check"; use_local = $false; cloud_provider = "gemini" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:3000/api/chat" -ContentType "application/json" -Body $body
```

## Compose File

This repo includes [podman-compose.yml](podman-compose.yml).

It defines:

- `frontend`
- `backend`
- `ollama`

It assumes the images are already built locally by Podman and then runs the stack from those images.

Current machine note:

- the compose file is aligned to the project
- this machine does not currently have a compose provider in `PATH`
- local management therefore runs through the verified plain-Podman fallback scripts

## Verification Status

The project has been verified with the following checks:

- backend modules compile successfully
- frontend multi-stage image build succeeds
- backend multi-stage image build succeeds
- backend smoke tests pass inside the container image
- backend health endpoint responds successfully
- frontend responds successfully from the containerized UI
- end-to-end `/api/chat` works through the frontend to the backend and Ollama
- proxied Swagger and ReDoc work through the frontend UI paths
- backend now supports OpenAI and Gemini cloud paths in addition to Ollama local routing
- frontend now exposes direct selection for `Local`, `OpenAI`, and `Gemini`
- live frontend proxy verification returned `200` for `/api/docs` and `/api/redoc`
- live end-to-end chat through `http://localhost:3000/api/chat` returned a successful Ollama response using `llama3.2:1b`
- live direct backend chat through `http://localhost:8000/chat` returned a successful Ollama response using `llama3.2:1b`
- live local-model selector path was rechecked through the frontend after the selector update
- current local timing sample through the frontend proxy was about `29s` for a short response on this machine
- OpenAI and Gemini UI routes are wired end to end, but live cloud success still depends on valid keys in `backend/.env`

## CI Workflow

The repo includes [.github/workflows/podman-local.yml](.github/workflows/podman-local.yml) for repeatable container-based verification in GitHub Actions.

## Common Issues

- `localhost` inside a container points to the container itself, not your host machine
- if host Ollama is used instead of the included containerized stack, set `OLLAMA_BASE_URL=http://host.containers.internal:11434`
- if compose mode cannot start, the PowerShell stack script automatically falls back to plain `podman run`
- if docs are opened from the frontend, use `http://localhost:3000/api/docs` and `http://localhost:3000/api/redoc`
- if the frontend cannot reach the backend, confirm the UI is running on `http://localhost:3000` and the backend is healthy on `http://localhost:8000/health`
- if cloud mode fails, the app falls back to Ollama when available
- if `podman logs` is empty, confirm the container is still running with `podman ps`
