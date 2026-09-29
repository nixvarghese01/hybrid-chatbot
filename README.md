# Hybrid Chatbot

A hybrid AI chatbot with a **React** frontend and a **FastAPI** backend. One chat API routes each prompt either to a **cloud model** (OpenAI or Gemini) or to a **local model** (Ollama). Private prompts stay on the local model, and if the cloud fails the router falls back to local. The whole stack runs in containers with **Podman**.

```
                    ┌────────────── Podman network ───────────────────────────────┐
 Browser ──:3000──▶ │ frontend (nginx + React) ──/api──▶ backend (FastAPI :8000)  │
                    │                                        │ ModelRouter         │
                    │                    ┌───────────────────┼──────────────┐      │
                    │                    ▼                   ▼              ▼      │
                    │              OpenAI API          Gemini API    ollama :11434 │
                    │              (cloud)             (cloud)       (local model) │
                    └─────────────────────────────────────────────────────────────┘
```

## Features

- **One chat endpoint** (`POST /chat`) for every model
- **Privacy-aware routing:** prompts with sensitive keywords never leave the machine
- **Automatic fallback:** primary cloud, then the other cloud, then local Ollama
- **Retries and timeouts** on every model client, and the chosen provider is logged
- **Model picker in the UI:** Local, OpenAI or Gemini for each message
- **Podman only:** multi-stage Containerfiles, a compose file, and PowerShell scripts that fall back to plain `podman run` when no compose provider is installed
- **OpenAPI docs** at `/api/docs` and `/api/redoc`

## Quick start

Prerequisites: Podman. For the cloud routes, an OpenAI and/or Gemini API key; the local route works without keys.

```powershell
git clone https://github.com/nixvarghese01/hybrid-chatbot.git
cd hybrid-chatbot
Copy-Item backend\.env.example backend\.env   # then add your API keys
.\scripts\container_stack.ps1                  # build images, start the stack, pull the Ollama model
```

Open http://localhost:3000.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 18, Vite 5, nginx (serves the UI and proxies `/api` to the backend) |
| Backend | FastAPI, Uvicorn, Pydantic, httpx |
| AI | OpenAI (`gpt-4o-mini` by default), Google Gemini (`gemini-2.5-flash`), Ollama (`llama3.2:1b`) |
| Containers | Podman, `podman compose`, multi-stage Containerfiles |
| Tests | pytest |

## How routing works

The request can set `use_local` and `cloud_provider`:

```json
POST /chat
{ "message": "Compare REST and gRPC", "use_local": false, "cloud_provider": "gemini" }
```
```json
{ "reply": "...", "provider": "gemini", "model_used": "gemini-2.5-flash", "fallback_used": false }
```

1. `use_local: true` → **Ollama**.
2. The message contains a sensitive keyword → **Ollama**. The keywords are: password, ssn, social security, bank account, credit card, private key, secret, confidential, medical record, personal data.
3. Otherwise → the **cloud provider**: the request's `cloud_provider`, or `CLOUD_PROVIDER` from `.env` (default `openai`).
4. If the chosen cloud provider fails, the router tries the other cloud provider, then Ollama. `fallback_used` is `true` in the response when this happens.

Complex-reasoning prompts (40+ words, or words like *analyze*, *compare*, *design*, *debug*) are detected and logged with each routing decision.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Send a message (see above) |
| `GET` | `/api/docs`, `/api/redoc`, `/api/openapi.json` | API documentation |

Through the frontend proxy, the same endpoints are under `http://localhost:3000/api/...`.

## Project structure

```text
.
|-- .github/workflows/podman-local.yml   CI: build and test with Podman (manual trigger)
|-- backend/
|   |-- services/
|   |   |-- router.py            routing, fallback and retry logic
|   |   |-- openai_client.py
|   |   |-- gemini_client.py
|   |   `-- ollama_client.py
|   |-- tests/test_main.py
|   |-- .env.example
|   |-- Containerfile
|   |-- main.py                  FastAPI app and request/response models
|   `-- requirements.txt
|-- frontend/
|   |-- nginx/default.conf       serves the UI, proxies /api to the backend
|   |-- src/                     App.jsx, main.jsx, styles.css
|   |-- .env.example
|   |-- Containerfile
|   |-- index.html
|   `-- package.json
|-- scripts/                     start, stop, status and clean helpers (PowerShell)
|-- podman-compose.yml
`-- README.md
```

## Configuration

Create `backend/.env` from the example:

```powershell
Copy-Item backend\.env.example backend\.env
```

```env
CLOUD_PROVIDER=openai            # openai or gemini: which cloud provider is tried first
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_OUTPUT_TOKENS=256

# Ollama on the host:
OLLAMA_BASE_URL=http://host.containers.internal:11434
# Ollama in the stack's own container:
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

- `container_stack.ps1` sets `OLLAMA_BASE_URL=http://ollama:11434` for the backend container automatically.
- The frontend calls `/api` through nginx, so the containerized UI needs no extra configuration.
- The UI can override the cloud provider on each message.
- `.env` files are git-ignored; only the `.env.example` templates are committed.

## Running with Podman

### Start

```powershell
.\scripts\container_stack.ps1
```

The script:
1. checks that Podman is installed (it doesn't install it for you)
2. stops old project containers and removes the project network
3. builds the backend and frontend multi-stage images
4. starts the stack with `podman compose` if a compose provider exists, otherwise with plain `podman run`
5. waits for Ollama and pulls the configured model if it's missing
6. checks backend health and frontend availability

### Day-to-day scripts

| Script | What it does |
|---|---|
| `start_stack.ps1` | Builds current images and starts the full stack |
| `stop_stack.ps1` | Stops project containers and removes the project network |
| `status_stack.ps1` | Shows container status plus frontend, docs and Ollama health |
| `clean_stack.ps1` | Stops the stack and removes runtime resources; keeps the Ollama model volume by default |

`clean_stack.ps1` options:
- `-RemoveImages`: remove the project images
- `-PruneDanglingImages`: remove dangling build layers
- `-RemoveOllamaVolume`: delete downloaded Ollama models, which are then re-downloaded on the next start

### URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/api/docs (or http://localhost:3000/api/docs) |
| ReDoc | http://localhost:8000/api/redoc |
| Backend health | http://localhost:8000/health |
| Ollama models | http://localhost:11434/api/tags |

With `llama3.2:1b` on a typical laptop CPU, short local replies take roughly 8–30 seconds, and the first request after a restart is slower while the model loads.

### Logs

```powershell
# with podman compose
podman compose -f podman-compose.yml logs -f backend     # or frontend / ollama

# with the plain-podman fallback
podman logs -f hybrid-chatbot-backend                    # or hybrid-chatbot-frontend / ollama
```

## Build and test

```powershell
# build the images
podman build --format docker -t hybrid-chatbot-api -f backend\Containerfile backend
podman build --format docker -t hybrid-chatbot-frontend -f frontend\Containerfile frontend

# run the backend tests inside the image
podman run --rm --workdir /app -v ${PWD}\backend\tests:/app/tests:Z hybrid-chatbot-api pytest -q tests/test_main.py
```

End-to-end check through the frontend proxy:

```powershell
$body = @{ message = "Say hello in one sentence."; use_local = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:3000/api/chat" -ContentType "application/json" -Body $body

$body = @{ message = "Reply with exactly: cloud-check"; use_local = $false; cloud_provider = "gemini" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:3000/api/chat" -ContentType "application/json" -Body $body
```

## CI

[`.github/workflows/podman-local.yml`](.github/workflows/podman-local.yml) builds the images and runs the tests with Podman on GitHub Actions. It runs on **manual trigger** (Actions → local-podman-ci → Run workflow).

## Troubleshooting

- Inside a container, `localhost` means the container itself. To reach Ollama on the host, use `http://host.containers.internal:11434`.
- If compose mode can't start, the start script falls back to plain `podman run` automatically.
- If the UI can't reach the backend, check http://localhost:8000/health.
- Cloud routes need valid API keys in `backend/.env`. Without them, requests fall back to Ollama.
- If `podman logs` shows nothing, check the container is still running with `podman ps`.
