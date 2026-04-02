"""
scrapers/http_client.py
───────────────────────
Shared async HTTP client layer.

Features
• Randomised User-Agent + Accept-Language header rotation
• Optional proxy support via env (HTTP_PROXY / HTTPS_PROXY)
• Tenacity retry: exponential backoff on network errors & 5xx
• Human-like randomised inter-request delays
• Full structured logging — zero raw print() calls
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryError,
)

log = logging.getLogger("scraper.http")

# ── User-Agent pool (desktop browsers, 2024-2025 vintage)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",

    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",

    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

_ACCEPT_LANGUAGES = [
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "pt-BR,pt;q=0.8,en;q=0.6",
    "pt;q=0.9,pt-BR;q=0.8,en-US;q=0.5",
]

_REFERERS = [
    "https://www.google.com.br/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "",  # no referer sometimes
]


def _stealth_headers() -> dict:
    return {
        "User-Agent":               random.choice(_USER_AGENTS),
        "Accept":                   "text/html,application/xhtml+xml,application/xml;"
                                    "q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":          random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding":          "gzip, deflate, br",
        "Connection":               "keep-alive",
        "Upgrade-Insecure-Requests":"1",
        "Sec-Fetch-Dest":           "document",
        "Sec-Fetch-Mode":           "navigate",
        "Sec-Fetch-Site":           "none",
        "Sec-Fetch-User":           "?1",
        "DNT":                      "1",
        **({"Referer": r} if (r := random.choice(_REFERERS)) else {}),
    }


class LotteryHttpClient:
    """
    Async context-manager wrapper around httpx.AsyncClient.

    Usage:
        async with LotteryHttpClient(proxies=...) as client:
            html = await client.get("https://...")
    """

    def __init__(
        self,
        proxies: Optional[dict] = None,
        timeout: float = 30.0,
        min_delay: float = 1.5,
        max_delay: float = 4.0,
    ) -> None:
        self._proxies   = proxies
        self._timeout   = timeout
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "LotteryHttpClient":
        transport_kwargs: dict = {}
        if self._proxies:
            log.debug(f"Proxy configured: {list(self._proxies.values())[0]}")

        self._client = httpx.AsyncClient(
            headers=_stealth_headers(),
            timeout=self._timeout,
            follow_redirects=True,
            http2=True,
            proxies=self._proxies,
            **transport_kwargs,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    async def _human_delay(self) -> None:
        delay = random.uniform(self._min_delay, self._max_delay)
        log.debug(f"Human delay: {delay:.2f}s")
        await asyncio.sleep(delay)

    @retry(
        retry=retry_if_exception_type((
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        )),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Async GET with:
        - Fresh stealth headers on every call
        - Human-like pre-request delay
        - Tenacity retry on network errors
        - 4xx/5xx raises httpx.HTTPStatusError
        """
        assert self._client is not None, "Use as async context manager"

        await self._human_delay()

        # Rotate headers per request
        self._client.headers.update(_stealth_headers())

        log.debug(f"GET {url}")
        response = await self._client.get(url, **kwargs)

        # Surface HTTP errors as exceptions so tenacity can see them
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            log.warning(f"Rate-limited (429) — backing off {retry_after}s")
            await asyncio.sleep(float(retry_after))
            response.raise_for_status()

        if response.status_code >= 500:
            log.warning(f"Server error {response.status_code} on {url}")
            response.raise_for_status()

        log.info(f"HTTP {response.status_code}  {url}")
        return response
