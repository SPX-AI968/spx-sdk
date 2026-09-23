"""Synchronous and asynchronous clients sharing validation and response handling."""

from __future__ import annotations

import json
import os
import warnings
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from pydantic import ValidationError

from .errors import (
    APIConnectionError,
    APIError,
    APIResponseError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from .types import (
    MAX_REQUEST_BYTES,
    DecisionRequest,
    DecisionResponse,
    Image,
    Model,
    Question,
)


def _configuration(api_key: str | None, base_url: str | None) -> tuple[str, dict[str, str]]:
    token = api_key if api_key is not None else os.getenv("SIMPLEX_API_TOKEN", "")
    if not token or not token.strip() or any(c.isspace() for c in token):
        raise ValueError("Set api_key or SIMPLEX_API_TOKEN to a non-empty token")
    origin = base_url or os.getenv("SIMPLEX_API_BASE") or "https://api.simplexai.net"
    url = httpx.URL(origin)
    if url.scheme not in ("http", "https") or not url.host or url.username or url.password:
        raise ValueError("base_url must be an HTTP(S) origin without credentials")
    if url.path not in ("", "/") or url.query or url.fragment:
        raise ValueError("base_url must be an origin, without /v1, query or fragment")
    if url.scheme == "http" and url.host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Use HTTPS for remote API servers")
    return str(url).rstrip("/"), {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "simplex-ai-sdk/0.1.0",
    }


def _payload(
    *,
    state: Any,
    questions: Mapping[str, Question | Mapping[str, Any]],
    model: Model,
    images: Sequence[Image | Mapping[str, Any]] | None,
    reasoning: bool,
    reasoning_max_tokens: int,
) -> bytes:
    request = DecisionRequest.model_validate(
        {
            "state": state,
            "questions": dict(questions),
            "model": model,
            "images": list(images or []),
            "reasoning": reasoning,
            "reasoning_max_tokens": reasoning_max_tokens,
        }
    )
    if request.reasoning:
        warnings.warn(
            "Reasoning is experimental and not recommended for normal use.",
            UserWarning,
            stacklevel=3,
        )
    # Do not exclude None recursively: null criteria and null state are meaningful.
    data = request.model_dump(mode="python")
    if not reasoning:
        data.pop("reasoning")
        data.pop("reasoning_max_tokens")
    if not request.images:
        data.pop("images")
    try:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError("Request must contain JSON-serializable, finite values") from exc
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError("Complete JSON request exceeds 15,000,000 bytes")
    return body


def _decode(response: httpx.Response) -> dict[str, Any]:
    if not 200 <= response.status_code < 300:
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        error = (
            AuthenticationError
            if response.status_code in (401, 403)
            else RateLimitError
            if response.status_code == 429
            else APIError
        )
        raise error(
            response.status_code,
            body=body,
            request_id=response.headers.get("x-request-id"),
            retry_after=response.headers.get("retry-after"),
        )
    try:
        data: Any = response.json()
    except ValueError as exc:
        raise APIResponseError("Expected a JSON response") from exc
    if not isinstance(data, dict):
        raise APIResponseError("Expected a JSON object")
    return data


def _decision(data: dict[str, Any]) -> DecisionResponse:
    try:
        return DecisionResponse.model_validate(data)
    except ValidationError as exc:
        raise APIResponseError("Response does not match the decision contract") from exc


class SimplexClient:
    """Reusable synchronous client. Close it or use a with block.

    Inference requests are never automatically retried. Redirects are not followed.
    `transport` is an optional httpx transport for tests or custom networking.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        origin, headers = _configuration(api_key, base_url)
        self._http = httpx.Client(
            base_url=origin,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    def _request(self, method: str, path: str, body: bytes | None = None) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, content=body)
        except httpx.TimeoutException as exc:
            raise APITimeoutError("Request timed out; inference may have completed") from exc
        except httpx.RequestError as exc:
            raise APIConnectionError("Could not complete the API request") from exc
        return _decode(response)

    def models(self) -> dict[str, Any]:
        """Fetch the current public model catalog and limits with authentication."""
        return self._request("GET", "/v1/models")

    def system_one(
        self,
        *,
        state: Any,
        questions: Mapping[str, Question | Mapping[str, Any]],
        model: Model = "spx-cd",
        images: Sequence[Image | Mapping[str, Any]] | None = None,
        reasoning: bool = False,
        reasoning_max_tokens: int = 512,
    ) -> DecisionResponse:
        """Run named decisions. Reasoning is experimental and disabled by default."""
        body = _payload(
            state=state,
            questions=questions,
            model=model,
            images=images,
            reasoning=reasoning,
            reasoning_max_tokens=reasoning_max_tokens,
        )
        return _decision(self._request("POST", "/v1/system-one", body))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SimplexClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncSimplexClient:
    """Asynchronous counterpart of SimplexClient; use async with or aclose()."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        origin, headers = _configuration(api_key, base_url)
        self._http = httpx.AsyncClient(
            base_url=origin,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    async def _request(self, method: str, path: str, body: bytes | None = None) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, content=body)
        except httpx.TimeoutException as exc:
            raise APITimeoutError("Request timed out; inference may have completed") from exc
        except httpx.RequestError as exc:
            raise APIConnectionError("Could not complete the API request") from exc
        return _decode(response)

    async def models(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/models")

    async def system_one(
        self,
        *,
        state: Any,
        questions: Mapping[str, Question | Mapping[str, Any]],
        model: Model = "spx-cd",
        images: Sequence[Image | Mapping[str, Any]] | None = None,
        reasoning: bool = False,
        reasoning_max_tokens: int = 512,
    ) -> DecisionResponse:
        body = _payload(
            state=state,
            questions=questions,
            model=model,
            images=images,
            reasoning=reasoning,
            reasoning_max_tokens=reasoning_max_tokens,
        )
        return _decision(await self._request("POST", "/v1/system-one", body))

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncSimplexClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
