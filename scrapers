"""
scrapers/base_scraper.py
────────────────────────
Abstract base class. All concrete scrapers inherit from this and implement
`parse_html()`. The base class handles fetch + error wrapping + result envelope.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from bs4 import BeautifulSoup

from models.schemas import DrawSession, ScrapedResult, SourceID
from scrapers.http_client import LotteryHttpClient

log = logging.getLogger("scraper.base")


class BaseScraper(ABC):
    source_id: SourceID
    url: str

    def __init__(self, client: LotteryHttpClient) -> None:
        self._client = client

    @abstractmethod
    def parse_html(self, html: str) -> List[DrawSession]:
        """
        Parse the raw HTML string and return a list of DrawSession objects.
        Must raise ValueError (or subclass) if the page structure is unexpected.
        """
        ...

    async def scrape(self) -> ScrapedResult:
        """Fetch the target URL and parse it. Returns a validated ScrapedResult."""
        run_id = str(uuid.uuid4())
        sessions: List[DrawSession] = []
        errors: List[str] = []

        try:
            response = await self._client.get(self.url)
            soup = BeautifulSoup(response.text, "lxml")
            sessions = self.parse_html(response.text)
            log.info(
                f"[{self.source_id.value}] Parsed {len(sessions)} session(s)"
            )
        except Exception as exc:
            msg = f"Scrape failed for {self.url}: {exc}"
            log.error(msg)
            errors.append(msg)

        return ScrapedResult(
            scrape_run_id=run_id,
            source_id=self.source_id,
            sessions=sessions,
            errors=errors,
        )

    # ── Shared parsing helpers ───────────────────────────────────────────────

    @staticmethod
    def _clean(text: Optional[str]) -> str:
        if not text:
            return ""
        return " ".join(text.split()).strip()

    @staticmethod
    def _extract_date_from_heading(heading: str) -> str:
        """Extract dd/mm/yyyy from headings like '...do dia 08/03/2026...'"""
        import re
        m = re.search(r"(\d{2}/\d{2}/\d{4})", heading)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_time_from_heading(heading: str) -> str:
        """Extract time token like '14h', '09:20', '11:00' from section headings."""
        import re
        m = re.search(r"(\d{1,2}[h:]\d{0,2})", heading, re.IGNORECASE)
        return m.group(1) if m else "00:00"
