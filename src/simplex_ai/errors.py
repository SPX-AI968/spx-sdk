"""SDK errors. HTTP details are available explicitly, not interpolated into logs."""

from typing import Any


class SimplexError(Exception):
    """Base class for transport, HTTP and response errors."""


class APIConnectionError(SimplexError):
    """Network failure; an inference may already have run. No automatic retries."""


class APITimeoutError(APIConnectionError):
    """Request timed out; execution status may be unknown."""


class APIResponseError(SimplexError):
    """Server returned invalid JSON or an incompatible response shape."""


class APIError(SimplexError):
    def __init__(
        self,
        status_code: int,
        *,
        body: Any = None,
        request_id: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(f"Simplex API returned HTTP {status_code}")
        self.status_code = status_code
        self.body = body
        self.request_id = request_id
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Missing, invalid, revoked or expired credentials (401/403)."""


class RateLimitError(APIError):
    """429; inspect retry_after before deciding whether to retry."""
