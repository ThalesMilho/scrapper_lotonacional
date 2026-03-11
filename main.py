"""
main.py
───────
Unified entry point.

Usage:
  python main.py              # oneshot (default)
  python main.py service      # scheduler daemon
  python main.py api          # FastAPI server (for maiorbichoo.com integration)
  python main.py all          # oneshot + API server together
"""

from __future__ import annotations

import asyncio
import sys

from config.logging_setup import setup_logging
from config.settings import settings


def main() -> None:
    setup_logging(level=settings.log_level, log_file=settings.log_file)

    import logging
    log = logging.getLogger("main")

    mode = sys.argv[1] if len(sys.argv) > 1 else settings.scraper_mode
    log.info(f"Starting in mode: {mode!r}")

    if mode == "oneshot":
        from service.orchestrator import LotteryOrchestrator
        asyncio.run(LotteryOrchestrator().run_all_once())

    elif mode == "service":
        from service.orchestrator import LotteryOrchestrator
        asyncio.run(LotteryOrchestrator().run_service())

    elif mode == "api":
        _run_api()

    elif mode == "all":
        # Run oneshot first, then start the API server
        from service.orchestrator import LotteryOrchestrator
        asyncio.run(LotteryOrchestrator().run_all_once())
        _run_api()

    else:
        log.error(f"Unknown mode '{mode}'. Use: oneshot | service | api | all")
        sys.exit(1)


def _run_api() -> None:
    import uvicorn
    from api.endpoints import create_app
    from storage.storage_manager import StorageManager

    storage = StorageManager(
        json_path=settings.storage_json_path,
        csv_path=settings.storage_csv_path,
    )
    app = create_app(storage=storage, api_secret_key=settings.api_secret_key)

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
