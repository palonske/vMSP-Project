"""
OCPI Hub Logging Middleware

Provides request/response logging for debugging and audit purposes.
Logs include:
- Request method, path, and headers
- Response status code and timing
- Masked authorization tokens for security
"""

import logging
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configure logger
logger = logging.getLogger("ocpi.requests")


def mask_token(token: str) -> str:
    """Mask a token for safe logging, showing only first and last 4 characters."""
    if not token or len(token) < 12:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


class OCPILoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all incoming requests and outgoing responses.

    Logs:
    - Request: method, path, client IP, masked auth token
    - Response: status code, processing time
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Extract and mask authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Token "):
            masked_auth = f"Token {mask_token(auth_header[6:])}"
        elif auth_header:
            masked_auth = mask_token(auth_header)
        else:
            masked_auth = "None"

        # Log the incoming request
        logger.info(
            f"Request: {method} {path} | Client: {client_ip} | Auth: {masked_auth}"
        )

        # Process the request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception and re-raise
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Error: {method} {path} | {type(e).__name__}: {str(e)} | {process_time:.2f}ms"
            )
            raise

        # Calculate processing time
        process_time = (time.time() - start_time) * 1000

        # Log the response
        logger.info(
            f"Response: {method} {path} | Status: {response.status_code} | {process_time:.2f}ms"
        )

        # Add processing time header for debugging
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        return response


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure logging for the OCPI Hub.

    Sets up a console handler with a standard format.
    Call this function during application startup.
    """
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure the OCPI logger
    ocpi_logger = logging.getLogger("ocpi")
    ocpi_logger.setLevel(level)
    ocpi_logger.addHandler(console_handler)

    # Prevent duplicate logs if called multiple times
    ocpi_logger.propagate = False
