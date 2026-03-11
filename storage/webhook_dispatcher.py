"""
storage/webhook_dispatcher.py
─────────────────────────────
Sends validated DrawSession data to the maiorbichoo.com webhook endpoint.

Security:  Bearer token from environment (never hard-coded)
Retry:     Tenacity exponential backoff on network failures
Schema:    WebhookPayload model enforces contract
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from models.schemas import DrawSession, WebhookPayload

log = logging.getLogger("webhook")


class WebhookDispatcher:
    def __init__(self, url: str, api_key: str, timeout: float = 15.0) -> None:
        self._url     = url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        self._timeout = timeout

    @retry(
        retry=retry_if_exception_type((
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.ConnectError,
        )),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    async def post_session(self, session: DrawSession) -> bool:
        """
        POST one DrawSession as a WebhookPayload.
        Returns True on success, False on 4xx client errors.
        Raises on network failures (after retries exhausted).
        """
        payload = WebhookPayload.from_session(session)

        log.info(
            f"[webhook] POST {session.source_id.value} "
            f"{session.draw_date} {session.draw_time} → {self._url}"
        )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._url,
                content=payload.model_dump_json(),
                headers=self._headers,
            )

        if 200 <= response.status_code < 300:
            log.info(f"[webhook] ✅ Delivered — HTTP {response.status_code}")
            return True

        if 400 <= response.status_code < 500:
            log.error(
                f"[webhook] ❌ Client error {response.status_code}: {response.text[:200]}"
            )
            return False

        # 5xx — raise so tenacity can retry
        response.raise_for_status()
        return False

    async def post_all_sessions(self, sessions: list[DrawSession]) -> dict:
        """Dispatch all sessions. Returns summary stats."""
        stats = {"sent": 0, "failed": 0, "skipped": 0}
        for session in sessions:
            try:
                ok = await self.post_session(session)
                if ok:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1
            except Exception as exc:
                log.error(f"[webhook] Failed for session {session.session_id}: {exc}")
                stats["failed"] += 1
        log.info(f"[webhook] Dispatch complete: {stats}")
        return stats
