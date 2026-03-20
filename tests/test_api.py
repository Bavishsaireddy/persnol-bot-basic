# tests/test_api.py
# Integration tests for the FastAPI gateway endpoints.
# Uses httpx.AsyncClient + FastAPI's TestClient — no live server needed.

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_mcp_result(text: str = "mocked"):
    result = MagicMock()
    result.text = text
    return [result]


# ─────────────────────────────────────────────────────────────
# /  health check
# ─────────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_root_returns_running(self):
        from gateway import app
        client   = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "agent"   in data
        assert "model"   in data
        assert "version" in data


# ─────────────────────────────────────────────────────────────
# /chat
# ─────────────────────────────────────────────────────────────

class TestChatEndpoint:

    @patch("gateway.call_tool", new_callable=AsyncMock, return_value=_make_mcp_result("Hello from Bavish!"))
    def test_chat_returns_response(self, _mock):
        from gateway import app
        client   = TestClient(app)
        response = client.post("/chat", json={
            "session_id": "test-chat",
            "message":    "Who are you?",
        })
        assert response.status_code == 200
        assert response.json()["response"] == "Hello from Bavish!"

    @patch("gateway.call_tool", new_callable=AsyncMock, return_value=[])
    def test_chat_empty_mcp_response_raises_500(self, _mock):
        from gateway import app
        client   = TestClient(app)
        response = client.post("/chat", json={
            "session_id": "test-empty",
            "message":    "hi",
        })
        assert response.status_code == 500

    def test_chat_missing_fields_returns_422(self):
        from gateway import app
        client   = TestClient(app)
        response = client.post("/chat", json={"message": "hi"})   # missing session_id
        assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# /clear-memory
# ─────────────────────────────────────────────────────────────

class TestClearMemoryEndpoint:

    @patch("gateway.call_tool", new_callable=AsyncMock,
           return_value=_make_mcp_result("Memory cleared for s1"))
    def test_clear_memory_ok(self, _mock):
        from gateway import app
        client   = TestClient(app)
        response = client.post("/clear-memory", json={"session_id": "s1"})
        assert response.status_code == 200
        assert "result" in response.json()

    def test_clear_memory_missing_session_returns_422(self):
        from gateway import app
        client   = TestClient(app)
        response = client.post("/clear-memory", json={})
        assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# /persona
# ─────────────────────────────────────────────────────────────

class TestPersonaEndpoint:

    @patch("gateway.call_tool", new_callable=AsyncMock,
           return_value=_make_mcp_result("persona: ...\nllm: ..."))
    def test_persona_returns_yaml_string(self, _mock):
        from gateway import app
        client   = TestClient(app)
        response = client.get("/persona")
        assert response.status_code == 200
        assert "persona" in response.json()


# ─────────────────────────────────────────────────────────────
# /webhook  (Telegram)
# ─────────────────────────────────────────────────────────────

class TestTelegramWebhook:

    def test_webhook_disabled_returns_false(self):
        """When telegram.enabled is false in config, webhook should reject."""
        with patch("gateway.TELEGRAM_ENABLED", False):
            from gateway import app
            client   = TestClient(app)
            response = client.post("/webhook", json={})
            assert response.status_code == 200
            assert response.json()["ok"] is False

    def test_webhook_missing_token_returns_false(self):
        with patch("gateway.TELEGRAM_ENABLED", True), \
             patch("gateway.TELEGRAM_TOKEN",   ""):
            from gateway import app
            client   = TestClient(app)
            response = client.post("/webhook", json={})
            assert response.status_code == 200
            assert response.json()["ok"] is False
