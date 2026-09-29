import logging
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.router import ModelRouter


load_dotenv()


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "Hybrid Chatbot API")
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message from the user.")
    use_local: bool = Field(
        default=False,
        description="Route directly to Ollama when true.",
    )
    cloud_provider: Literal["openai", "gemini"] | None = Field(
        default=None,
        description="Override the configured cloud provider when not using the local model.",
    )


class ChatResponse(BaseModel):
    reply: str
    provider: Literal["openai", "gemini", "ollama"]
    model_used: str
    fallback_used: bool = False


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


settings = Settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)
router = ModelRouter()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="FastAPI backend for a hybrid AI chatbot using OpenAI, Gemini, and Ollama.",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/api/docs")


@app.get("/docs", include_in_schema=False)
async def swagger_redirect() -> RedirectResponse:
    return RedirectResponse(url="/api/docs")


@app.get("/redoc", include_in_schema=False)
async def redoc_redirect() -> RedirectResponse:
    return RedirectResponse(url="/api/redoc")


@app.get("/openapi.json", include_in_schema=False)
async def openapi_compat() -> dict:
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "environment": settings.app_env}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await router.chat(
            message=request.message,
            use_local=request.use_local,
            cloud_provider_override=request.cloud_provider,
        )
        return ChatResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while processing chat request.")
        raise HTTPException(status_code=500, detail="Internal server error.") from exc
