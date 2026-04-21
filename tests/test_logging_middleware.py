"""
Tests for the OCPI Logging Middleware.

Tests include:
- Token masking functionality
- Middleware integration with FastAPI
- Logging output verification
"""

import pytest
import logging
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import mask_token, OCPILoggingMiddleware, setup_logging


class TestTokenMasking:
    """Test the token masking utility function."""

    def test_mask_normal_token(self):
        """Test masking a normal-length token."""
        token = "abcd1234efgh5678ijkl"
        result = mask_token(token)
        assert result == "abcd...ijkl"

    def test_mask_short_token(self):
        """Test masking a short token (less than 12 chars)."""
        token = "short"
        result = mask_token(token)
        assert result == "***"

    def test_mask_empty_token(self):
        """Test masking an empty token."""
        token = ""
        result = mask_token(token)
        assert result == "***"

    def test_mask_none_token(self):
        """Test masking a None token."""
        result = mask_token(None)
        assert result == "***"

    def test_mask_exact_12_char_token(self):
        """Test masking a token with exactly 12 characters."""
        token = "123456789012"
        result = mask_token(token)
        assert result == "1234...9012"

    def test_mask_11_char_token(self):
        """Test masking a token with 11 characters (below threshold)."""
        token = "12345678901"
        result = mask_token(token)
        assert result == "***"


class TestLoggingMiddleware:
    """Test the OCPI logging middleware."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the logging middleware."""
        app = FastAPI()
        app.add_middleware(OCPILoggingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    @pytest.fixture
    def client(self, test_app):
        """Create a test client for the app."""
        return TestClient(test_app, raise_server_exceptions=False)

    def test_middleware_adds_process_time_header(self, client):
        """Test that middleware adds X-Process-Time header to responses."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Process-Time" in response.headers
        assert "ms" in response.headers["X-Process-Time"]

    def test_middleware_logs_request(self, client, caplog):
        """Test that middleware logs incoming requests."""
        with caplog.at_level(logging.INFO, logger="ocpi.requests"):
            response = client.get("/test")

        assert response.status_code == 200
        # Check that request was logged
        request_logs = [r for r in caplog.records if "Request:" in r.message]
        assert len(request_logs) >= 1
        assert "GET" in request_logs[0].message
        assert "/test" in request_logs[0].message

    def test_middleware_logs_response(self, client, caplog):
        """Test that middleware logs outgoing responses."""
        with caplog.at_level(logging.INFO, logger="ocpi.requests"):
            response = client.get("/test")

        assert response.status_code == 200
        # Check that response was logged
        response_logs = [r for r in caplog.records if "Response:" in r.message]
        assert len(response_logs) >= 1
        assert "200" in response_logs[0].message

    def test_middleware_masks_auth_token(self, client, caplog):
        """Test that authorization tokens are masked in logs."""
        with caplog.at_level(logging.INFO, logger="ocpi.requests"):
            response = client.get(
                "/test",
                headers={"Authorization": "Token abcd1234efgh5678ijkl9999"}
            )

        assert response.status_code == 200
        # Find the request log
        request_logs = [r for r in caplog.records if "Request:" in r.message]
        assert len(request_logs) >= 1
        # Token should be masked
        assert "abcd...9999" in request_logs[0].message
        # Full token should NOT appear
        assert "abcd1234efgh5678ijkl9999" not in request_logs[0].message

    def test_middleware_handles_no_auth(self, client, caplog):
        """Test that middleware handles requests without auth header."""
        with caplog.at_level(logging.INFO, logger="ocpi.requests"):
            response = client.get("/test")

        assert response.status_code == 200
        request_logs = [r for r in caplog.records if "Request:" in r.message]
        assert len(request_logs) >= 1
        assert "Auth: None" in request_logs[0].message


class TestSetupLogging:
    """Test the logging setup function."""

    def test_setup_logging_creates_logger(self):
        """Test that setup_logging configures the OCPI logger."""
        setup_logging(level=logging.DEBUG)

        logger = logging.getLogger("ocpi")
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) > 0

    def test_setup_logging_prevents_propagation(self):
        """Test that the logger doesn't propagate to root."""
        setup_logging()

        logger = logging.getLogger("ocpi")
        assert logger.propagate is False
