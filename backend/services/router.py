import asyncio
import logging
import os

from fastapi import HTTPException

from services.gemini_client import GeminiClient
from services.ollama_client import OllamaClient
from services.openai_client import OpenAIClient


logger = logging.getLogger(__name__)

SENSITIVE_KEYWORDS = {
    "password",
    "ssn",
    "social security",
    "bank account",
    "credit card",
    "private key",
    "secret",
    "confidential",
    "medical record",
    "personal data",
}

COMPLEX_REASONING_KEYWORDS = {
    "analyze",
    "compare",
    "reason",
    "step by step",
    "tradeoff",
    "architecture",
    "optimize",
    "debug",
    "evaluate",
    "design",
}


class ModelRouter:
    def __init__(self) -> None:
        self.ollama_client = OllamaClient()
        self._openai_client: OpenAIClient | None = None
        self._gemini_client: GeminiClient | None = None
        self.cloud_provider = os.getenv("CLOUD_PROVIDER", "openai").strip().lower()
        self.request_timeout = float(os.getenv("ROUTER_TIMEOUT_SECONDS", "75"))
        self.max_retries = int(os.getenv("ROUTER_RETRY_COUNT", "1"))
        self.retry_delay_seconds = float(os.getenv("ROUTER_RETRY_DELAY_SECONDS", "1"))

    def _effective_cloud_provider(self, override: str | None) -> str:
        provider = (override or self.cloud_provider or "openai").strip().lower()
        if provider not in {"openai", "gemini"}:
            return "openai"
        return provider

    @property
    def openai_client(self) -> OpenAIClient:
        if self._openai_client is None:
            self._openai_client = OpenAIClient()
        return self._openai_client

    @property
    def gemini_client(self) -> GeminiClient:
        if self._gemini_client is None:
            self._gemini_client = GeminiClient()
        return self._gemini_client

    def _contains_sensitive_keywords(self, message: str) -> bool:
        normalized = message.lower()
        return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)

    def _requires_complex_reasoning(self, message: str) -> bool:
        normalized = message.lower()
        if len(message.split()) >= 40:
            return True
        return any(keyword in normalized for keyword in COMPLEX_REASONING_KEYWORDS)

    def _select_primary_model(
        self,
        message: str,
        use_local: bool,
        cloud_provider_override: str | None,
    ) -> str:
        effective_cloud_provider = self._effective_cloud_provider(cloud_provider_override)
        if use_local:
            return "ollama"
        if self._contains_sensitive_keywords(message):
            return "ollama"
        if self._requires_complex_reasoning(message):
            return effective_cloud_provider
        return effective_cloud_provider

    def _cloud_fallback_order(self, primary_model: str) -> list[str]:
        order: list[str] = []
        if primary_model == "openai":
            order = ["openai", "gemini", "ollama"]
        elif primary_model == "gemini":
            order = ["gemini", "openai", "ollama"]
        else:
            order = ["ollama"]
        return order

    async def _call_with_retry(self, client_name: str, message: str) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                if client_name == "openai":
                    logger.info("Attempt %s using OpenAI.", attempt)
                    result = await asyncio.wait_for(
                        self.openai_client.chat(message),
                        timeout=self.request_timeout,
                    )
                elif client_name == "gemini":
                    logger.info("Attempt %s using Gemini.", attempt)
                    result = await asyncio.wait_for(
                        self.gemini_client.chat(message),
                        timeout=self.request_timeout,
                    )
                else:
                    logger.info("Attempt %s using Ollama.", attempt)
                    result = await asyncio.wait_for(
                        self.ollama_client.chat(message),
                        timeout=self.request_timeout,
                    )

                logger.info(
                    "Model used: provider=%s model=%s fallback=%s",
                    result.get("provider"),
                    result.get("model_used"),
                    result.get("fallback_used", False),
                )
                return result
            except asyncio.TimeoutError as exc:
                last_error = TimeoutError(
                    f"{client_name} timed out after {self.request_timeout} seconds."
                )
                logger.warning(
                    "%s timed out on attempt %s/%s.",
                    client_name,
                    attempt,
                    self.max_retries + 1,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "%s failed on attempt %s/%s: %s",
                    client_name,
                    attempt,
                    self.max_retries + 1,
                    exc,
                )

            if attempt <= self.max_retries:
                await asyncio.sleep(self.retry_delay_seconds * attempt)

        raise RuntimeError(f"{client_name} failed after retries.") from last_error

    async def chat(
        self,
        message: str,
        use_local: bool,
        cloud_provider_override: str | None = None,
    ) -> dict:
        effective_cloud_provider = self._effective_cloud_provider(cloud_provider_override)
        primary_model = self._select_primary_model(message, use_local, cloud_provider_override)
        fallback_chain = self._cloud_fallback_order(primary_model)

        logger.info(
            "Routing decision: primary_model=%s use_local=%s sensitive=%s complex=%s cloud_provider=%s",
            primary_model,
            use_local,
            self._contains_sensitive_keywords(message),
            self._requires_complex_reasoning(message),
            effective_cloud_provider,
        )

        errors: list[str] = []

        for index, model_name in enumerate(fallback_chain):
            try:
                response = await self._call_with_retry(model_name, message)
                if index > 0:
                    response["fallback_used"] = True
                    logger.info(
                        "Fallback succeeded: provider=%s model=%s",
                        response.get("provider"),
                        response.get("model_used"),
                    )
                return response
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
                if index < len(fallback_chain) - 1:
                    logger.warning(
                        "Primary/fallback model %s failed, trying next option: %s",
                        model_name,
                        exc,
                    )
                else:
                    logger.exception("All configured model routes failed.")

        raise HTTPException(
            status_code=502,
            detail="All model routes failed. " + " | ".join(errors),
        )
