"""
service/orchestrator.py
───────────────────────
Central orchestrator that ties together:
  - All four scrapers
  - Storage manager
  - Webhook dispatcher
  - APScheduler (service mode)

Modes:
  oneshot  → Runs all scrapers once, saves, dispatches, exits.
  service  → Stays alive, fires scrapers on configured schedules.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from models.schemas import SourceID
from scrapers.http_client import LotteryHttpClient
from scrapers.nacional_scraper import LoterianacionalScraper
from scrapers.resultado_facil_scraper import (
    make_boa_sorte_scraper,
    make_look_loterias_scraper,
    make_bicho_rj_scraper,
)
from storage.storage_manager import StorageManager
from storage.webhook_dispatcher import WebhookDispatcher

log = logging.getLogger("orchestrator")


class LotteryOrchestrator:
    def __init__(self) -> None:
        self._storage = StorageManager(
            json_path=settings.storage_json_path,
            csv_path=settings.storage_csv_path,
        )
        self._webhook = WebhookDispatcher(
            url=settings.webhook_url,
            api_key=settings.webhook_api_key,
        )

    # ── Single pass ──────────────────────────────────────────────────────────

    async def run_all_once(self) -> None:
        """Scrape all four sources, save, and dispatch webhooks."""
        log.info("=" * 60)
        log.info("Orchestrator: Starting full scrape pass")
        log.info("=" * 60)

        async with LotteryHttpClient(proxies=settings.proxies) as client:
            scrapers = [
                LoterianacionalScraper(client),
                make_boa_sorte_scraper(client),
                make_look_loterias_scraper(client),
                make_bicho_rj_scraper(client),
            ]

            # Run all scrapers — staggered to be polite
            for scraper in scrapers:
                log.info(f"Scraping: {scraper.source_id.value} → {scraper.url}")
                try:
                    result = await scraper.scrape()

                    if result.errors:
                        for e in result.errors:
                            log.error(f"  Error: {e}")

                    new_count = self._storage.save(result)

                    if new_count > 0:
                        # Dispatch only new sessions
                        new_sessions = result.sessions[-new_count:] if new_count else []
                        stats = await self._webhook.post_all_sessions(new_sessions)
                        log.info(f"  Webhook: {stats}")
                    else:
                        log.info("  No new sessions to dispatch.")

                except Exception as exc:
                    log.error(f"  Scraper {scraper.source_id.value} failed: {exc}")

        log.info("Orchestrator: Pass complete.")

    async def run_nacional_once(self) -> None:
        await self._run_single(SourceID.LOTERIA_NACIONAL)

    async def run_resultado_facil_once(self) -> None:
        for source in (SourceID.BOA_SORTE, SourceID.LOOK_LOTERIAS, SourceID.BICHO_RJ):
            await self._run_single(source)

    async def _run_single(self, source_id: SourceID) -> None:
        async with LotteryHttpClient(proxies=settings.proxies) as client:
            scraper_map = {
                SourceID.LOTERIA_NACIONAL: lambda c: LoterianacionalScraper(c),
                SourceID.BOA_SORTE:        make_boa_sorte_scraper,
                SourceID.LOOK_LOTERIAS:    make_look_loterias_scraper,
                SourceID.BICHO_RJ:         make_bicho_rj_scraper,
            }
            scraper = scraper_map[source_id](client)
            result = await scraper.scrape()
            new_count = self._storage.save(result)
            if new_count > 0:
                await self._webhook.post_all_sessions(result.sessions[-new_count:])

    # ── Service mode ─────────────────────────────────────────────────────────

    async def run_service(self) -> None:
        scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

        # Nacional schedule (e.g. 11:30, 14:30, 19:30)
        for time_str in settings.schedule_nacional:
            h, m = time_str.split(":")
            scheduler.add_job(
                self.run_nacional_once,
                CronTrigger(hour=int(h), minute=int(m)),
                id=f"nacional_{time_str}",
                replace_existing=True,
            )
            log.info(f"Scheduled Nacional at {time_str} BRT")

        # ResultadoFácil schedule
        for time_str in settings.schedule_resultado_facil:
            h, m = time_str.split(":")
            scheduler.add_job(
                self.run_resultado_facil_once,
                CronTrigger(hour=int(h), minute=int(m)),
                id=f"rf_{time_str}",
                replace_existing=True,
            )
            log.info(f"Scheduled ResultadoFácil at {time_str} BRT")

        scheduler.start()
        log.info("Orchestrator: Service mode active — waiting for scheduled jobs.")

        # Keep event loop alive
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            log.info("Orchestrator: Shutting down.")
            scheduler.shutdown()
