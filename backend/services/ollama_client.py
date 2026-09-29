import logging
import os
from asyncio import sleep

import httpx


logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://host.containers.internal:11434",
        )
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
        self.timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
        self.max_retries = int(os.getenv("MODEL_RETRY_COUNT", "2"))
        self.retry_delay_seconds = float(os.getenv("MODEL_RETRY_DELAY_SECONDS", "1"))
        self.max_tokens = int(os.getenv("OLLAMA_NUM_PREDICT", "192"))

    async def chat(self, message: str) -> dict:
        payload = {
            "model": self.model,
            "prompt": message,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
            },
        }

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    data = response.json()

                output_text = str(data.get("response", "")).strip()
                if not output_text:
                    raise RuntimeError("Ollama returned an empty response.")

                return {
                    "reply": output_text,
                    "provider": "ollama",
                    "model_used": str(data.get("model", self.model)),
                    "fallback_used": False,
                }
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Ollama request failed on attempt %s/%s via %s: %s",
                    attempt,
                    self.max_retries + 1,
                    self.base_url,
                    exc,
                )

            if attempt <= self.max_retries:
                await sleep(self.retry_delay_seconds * attempt)

        logger.exception("Ollama request failed after retries.", exc_info=last_error)
        raise RuntimeError("Ollama request failed after retries.") from last_error
