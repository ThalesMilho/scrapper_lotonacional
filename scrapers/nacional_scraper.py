"""
scrapers/nacional_scraper.py
────────────────────────────
Scraper for www.lotonacional.com.br

The site is SSR — draw results live in a standard <table> inside the HTML.
The existing phase2_stealth_scraper.py in the repo also targets this site;
this rewrite integrates it cleanly into the new architecture.

Page structure observed (from Phase 1 recon + repo code):
  - Results table with columns: Prêmio | Milhar | Grupo | Bicho
  - Draw ID / date visible in a heading element
  - Derives complements via 9999 - milhar rule (preserved from original code)
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from models.schemas import DrawEntry, DrawSession, SourceID
from scrapers.base_scraper import BaseScraper
from scrapers.http_client import LotteryHttpClient

log = logging.getLogger("scraper.nacional")

NACIONAL_URL = "https://www.lotonacional.com.br/loteria-federal/resultados/"

class LoterianacionalScraper(BaseScraper):
    source_id = SourceID.LOTERIA_NACIONAL
    url = NACIONAL_URL

    def __init__(self, client: LotteryHttpClient) -> None:
        super().__init__(client)

    def parse_html(self, html: str) -> List[DrawSession]:
        soup = BeautifulSoup(html, "lxml")
        sessions: List[DrawSession] = []

        # ── Find all result containers
        # The page uses <table> elements; we look for the one(s) containing
        # milhar / bicho data. We try multiple selector strategies in order.
        tables = [t for t in soup.find_all("table") if "Prêmio" in t.get_text()]


        if not tables:
            log.warning("Nacional: No result tables found on page.")
            return sessions

        for table in tables:
            # Try to find the nearest heading for date/time
            heading_el = self._nearest_heading(table)
            heading_text = self._clean(heading_el.get_text()) if heading_el else ""

            draw_date = self._extract_date_from_heading(heading_text)
            draw_time = self._extract_time_from_heading(heading_text)

            # If still no date, look for it anywhere near the table
            if not draw_date:
                draw_date = self._scan_for_date(soup)

            if not draw_date:
                log.debug("Nacional: Could not resolve draw date — skipping table.")
                continue

            entries = self._parse_table(table)
            if not entries:
                continue

            try:
                session = DrawSession(
                    source_id=self.source_id,
                    source_url=self.url,
                    draw_date=draw_date,
                    draw_time=draw_time or "00:00",
                    draw_label=heading_text,
                    state=None,
                    banca="Loteria Nacional",
                    entries=entries,
                )
                sessions.append(session)
                log.info(
                    f"Nacional: draw {draw_date} {draw_time} "
                    f"— 1st milhar={session.first_milhar}"
                )
            except Exception as exc:
                log.warning(f"Nacional: Validation error: {exc}")

        return sessions

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _find_result_tables(soup: BeautifulSoup) -> List[Tag]:
        """
        Heuristic: a result table always contains cells with 4-digit numbers
        and bicho animal names. Return all matching tables.
        """
        candidates = []
        for table in soup.find_all("table"):
            text = table.get_text()
            # Must contain a 4-digit number AND at least one known bicho
            if re.search(r"\b\d{4}\b", text) and re.search(
                r"\b(Avestruz|Águia|Burro|Borboleta|Cachorro|Cabra|Carneiro|Camelo"
                r"|Cobra|Coelho|Cavalo|Elefante|Galo|Gato|Jacaré|Leão|Macaco|Pavão"
                r"|Peru|Porco|Tigre|Touro|Urso|Veado|Vaca)\b",
                text,
                re.IGNORECASE,
            ):
                candidates.append(table)
        if not candidates:
            candidates = [t for t in soup.find_all("table")
                          if "milhar" in t.get_text().lower()]
        return candidates

    @staticmethod
    def _nearest_heading(table: Tag) -> Optional[Tag]:
        """Walk backwards from the table to find h1/h2/h3/h4."""
        el = table.find_previous_sibling()
        for _ in range(10):
            if el is None:
                break
            if el.name in ("h1", "h2", "h3", "h4"):
                return el
            el = el.find_previous_sibling()
        # Fallback: go up a level and try again
        parent = table.parent
        if parent:
            for tag in parent.find_all(["h1", "h2", "h3", "h4"]):
                return tag
        return None

    @staticmethod
    def _scan_for_date(soup: BeautifulSoup) -> str:
        """Last-resort: scan all text for a dd/mm/yyyy date."""
        for tag in soup.find_all(True):
            m = re.search(r"(\d{2}/\d{2}/\d{4})", tag.get_text())
            if m:
                return m.group(1)
        return ""

    def _parse_table(self, table: Tag) -> List[DrawEntry]:
        entries: List[DrawEntry] = []
        rows = table.find_all("tr")

        for row in rows[1:]:
            cols = [self._clean(td.get_text()) for td in row.find_all("td")]
            if len(cols) < 4:
                continue

            premio_raw, milhar_raw, grupo_raw, bicho_raw = cols[:4]

            # Skip soma/mult derived rows
            if any(s in premio_raw.lower() for s in ("soma", "mult")):
                continue

            premio_num = re.sub(r"[^\d]", "", premio_raw)
            grupo_str  = re.sub(r"[^\d]", "", grupo_raw)
            milhar_str = re.sub(r"[^\d]", "", milhar_raw).zfill(4)

            if not premio_num or not grupo_str or not milhar_str:
                continue

            try:
                entries.append(
                    DrawEntry(
                        premio=int(premio_num),
                        milhar=milhar_str,
                        centena=milhar_str[-3:],
                        dezena=milhar_str[-2:],
                        grupo=int(grupo_str),
                        bicho=bicho_raw,
                    )
                )
            except Exception as exc:
                log.debug(f"Nacional row skip: {exc}")

        return entries
