import asyncio
import logging
import os
from asyncio import sleep

from google import genai
from google.genai import types


logger = logging.getLogger(__name__)


def _clean_api_key(raw_key: str) -> str:
    return raw_key.strip().split()[0] if raw_key.strip() else ""


class GeminiClient:
    def __init__(self) -> None:
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        api_key = _clean_api_key(os.getenv("GEMINI_API_KEY", ""))
        self.timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
        self.max_retries = int(os.getenv("MODEL_RETRY_COUNT", "2"))
        self.retry_delay_seconds = float(os.getenv("MODEL_RETRY_DELAY_SECONDS", "1"))
        self.max_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "256"))

        if not api_key or api_key.startswith("your_"):
            raise ValueError("GEMINI_API_KEY is not configured with a real value.")

        self.client = genai.Client(api_key=api_key)

    def _generate_content(self, message: str):
        return self.client.models.generate_content(
            model=self.model,
            contents=message,
            config=types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
            ),
        )

    async def chat(self, message: str) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self._generate_content, message),
                    timeout=self.timeout,
                )
                output_text = (getattr(response, "text", "") or "").strip()
                if not output_text:
                    raise RuntimeError("Gemini returned an empty response.")

                return {
                    "reply": output_text,
                    "provider": "gemini",
                    "model_used": self.model,
                    "fallback_used": False,
                }
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini request failed on attempt %s/%s: %s",
                    attempt,
                    self.max_retries + 1,
                    exc,
                )

            if attempt <= self.max_retries:
                await sleep(self.retry_delay_seconds * attempt)

        logger.exception("Gemini request failed after retries.", exc_info=last_error)
        raise RuntimeError("Gemini request failed after retries.") from last_error
