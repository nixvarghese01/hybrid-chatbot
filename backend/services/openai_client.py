import logging
import os
from asyncio import sleep

from openai import APIError, AsyncOpenAI


logger = logging.getLogger(__name__)


def _clean_api_key(raw_key: str) -> str:
    return raw_key.strip().split()[0] if raw_key.strip() else ""


class OpenAIClient:
    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        api_key = _clean_api_key(os.getenv("OPENAI_API_KEY", ""))
        self.timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
        self.max_retries = int(os.getenv("MODEL_RETRY_COUNT", "2"))
        self.retry_delay_seconds = float(os.getenv("MODEL_RETRY_DELAY_SECONDS", "1"))

        if not api_key or api_key.startswith("your_"):
            raise ValueError("OPENAI_API_KEY is not configured with a real value.")

        self.client = AsyncOpenAI(api_key=api_key, timeout=self.timeout)

    async def chat(self, message: str) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                response = await self.client.responses.create(
                    model=self.model,
                    input=message,
                )
                output_text = (response.output_text or "").strip()
                if not output_text:
                    raise RuntimeError("OpenAI returned an empty response.")

                return {
                    "reply": output_text,
                    "provider": "openai",
                    "model_used": getattr(response, "model", self.model),
                    "fallback_used": False,
                }
            except APIError as exc:
                last_error = exc
                logger.warning(
                    "OpenAI API request failed on attempt %s/%s: %s",
                    attempt,
                    self.max_retries + 1,
                    exc,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Unexpected OpenAI client error on attempt %s/%s: %s",
                    attempt,
                    self.max_retries + 1,
                    exc,
                )

            if attempt <= self.max_retries:
                await sleep(self.retry_delay_seconds * attempt)

        logger.exception("OpenAI request failed after retries.", exc_info=last_error)
        raise RuntimeError("OpenAI request failed after retries.") from last_error
