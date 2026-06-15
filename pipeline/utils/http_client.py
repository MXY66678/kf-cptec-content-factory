"""Shared async HTTP client with rate limiting and retry support."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from loguru import logger as log

from pipeline.utils.retry import api_retry_decorator
from config import MAX_RETRIES


class APIClient:
    """Reusable HTTP client with exponential backoff and 429 handling.

    Supports both sync and async usage. By default creates a new client per call
    to avoid asyncio event-loop conflicts in threaded contexts.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._default_headers = headers or {}
        if api_key:
            self._default_headers.setdefault("Authorization", f"Bearer {api_key}")

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._default_headers,
        )

    def _build_async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._default_headers,
        )

    @api_retry_decorator()
    def post_sync(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Synchronous POST with retry and 429 handling."""
        url = self.base_url + endpoint
        headers = {**self._default_headers, **(extra_headers or {})}

        with self._build_client() as client:
            response = client.post(url, json=json_data, headers=headers)

            if response.status_code == 429:
                log.warning("429 rate limit hit for {}", endpoint)
                response.raise_for_status()

            response.raise_for_status()
            return response.json()

    @api_retry_decorator()
    def get_sync(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Synchronous GET with retry."""
        with self._build_client() as client:
            response = client.get(endpoint, params=params)
            if response.status_code == 429:
                log.warning("429 rate limit hit for {}", endpoint)
                response.raise_for_status()
            response.raise_for_status()
            return response.json()

    async def post_async(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Asynchronous POST stub — uses sync internally for now."""
        return self.post_sync(endpoint, json_data, extra_headers)

    async def get_async(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Asynchronous GET stub."""
        return self.get_sync(endpoint, params)
