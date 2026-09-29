from pathlib import Path
import sys

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


client = TestClient(main.app)


class SuccessfulRouter:
    async def chat(
        self,
        message: str,
        use_local: bool,
        cloud_provider_override=None,
    ) -> dict:
        if use_local:
            return {
                "reply": f"local: {message}",
                "provider": "ollama",
                "model_used": "llama3.2:1b",
                "fallback_used": False,
            }
        return {
            "reply": f"cloud: {message}",
            "provider": "openai",
            "model_used": "gpt-4o-mini",
            "fallback_used": False,
        }


class FallbackRouter:
    async def chat(
        self,
        message: str,
        use_local: bool,
        cloud_provider_override=None,
    ) -> dict:
        return {
            "reply": f"fallback: {message}",
            "provider": "ollama",
            "model_used": "llama3.2:1b",
            "fallback_used": True,
        }


class FailingRouter:
    async def chat(
        self,
        message: str,
        use_local: bool,
        cloud_provider_override=None,
    ) -> dict:
        raise RuntimeError("router failure")


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_uses_openai_path_by_default(monkeypatch) -> None:
    monkeypatch.setattr(main, "router", SuccessfulRouter())

    response = client.post("/chat", json={"message": "hello", "use_local": False})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "cloud: hello",
        "provider": "openai",
        "model_used": "gpt-4o-mini",
        "fallback_used": False,
    }


def test_chat_allows_gemini_provider(monkeypatch) -> None:
    class GeminiRouter:
        async def chat(
            self,
            message: str,
            use_local: bool,
            cloud_provider_override=None,
        ) -> dict:
            return {
                "reply": f"gemini: {message}",
                "provider": "gemini",
                "model_used": "gemini-2.5-flash",
                "fallback_used": False,
            }

    monkeypatch.setattr(main, "router", GeminiRouter())

    response = client.post("/chat", json={"message": "hello", "use_local": False})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "gemini: hello",
        "provider": "gemini",
        "model_used": "gemini-2.5-flash",
        "fallback_used": False,
    }


def test_chat_accepts_cloud_provider_override(monkeypatch) -> None:
    class OverrideRouter:
        async def chat(self, message: str, use_local: bool, cloud_provider_override=None) -> dict:
            return {
                "reply": f"override: {cloud_provider_override}",
                "provider": cloud_provider_override,
                "model_used": "override-model",
                "fallback_used": False,
            }

    monkeypatch.setattr(main, "router", OverrideRouter())

    response = client.post(
        "/chat",
        json={"message": "hello", "use_local": False, "cloud_provider": "gemini"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "override: gemini",
        "provider": "gemini",
        "model_used": "override-model",
        "fallback_used": False,
    }


def test_chat_uses_local_path_when_requested(monkeypatch) -> None:
    monkeypatch.setattr(main, "router", SuccessfulRouter())

    response = client.post("/chat", json={"message": "hello", "use_local": True})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "local: hello",
        "provider": "ollama",
        "model_used": "llama3.2:1b",
        "fallback_used": False,
    }


def test_chat_returns_fallback_response(monkeypatch) -> None:
    monkeypatch.setattr(main, "router", FallbackRouter())

    response = client.post("/chat", json={"message": "hello", "use_local": False})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "fallback: hello",
        "provider": "ollama",
        "model_used": "llama3.2:1b",
        "fallback_used": True,
    }


def test_chat_returns_500_on_unexpected_router_error(monkeypatch) -> None:
    monkeypatch.setattr(main, "router", FailingRouter())

    response = client.post("/chat", json={"message": "hello", "use_local": False})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}


def test_chat_rejects_empty_message() -> None:
    response = client.post("/chat", json={"message": "", "use_local": False})

    assert response.status_code == 422
