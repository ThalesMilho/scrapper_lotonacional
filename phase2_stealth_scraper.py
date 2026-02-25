import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from playwright.async_api import Browser, BrowserContext, Page, Route, TimeoutError, async_playwright

try:
    from playwright_stealth import stealth_async
except Exception:  # pragma: no cover
    stealth_async = None


logger = logging.getLogger("lotonacional.phase2")


class LotteryDraw(BaseModel):
    source_url: str
    extracted_at_utc: datetime
    draw_id: Optional[str] = None
    draw_date: Optional[str] = None
    numbers: list[int] = Field(min_length=5, max_length=25)
    derived_numbers: list[str] = Field(default_factory=list)

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        if any((not isinstance(n, int)) for n in v):
            raise ValueError("numbers must be ints")
        if len(v) != 5:
            raise ValueError("numbers must contain exactly 5 items")
        if any((n < 0 or n > 9999) for n in v):
            raise ValueError("numbers out of expected range 0-9999")
        return v

    @field_validator("derived_numbers")
    @classmethod
    def validate_derived_numbers(cls, v: list[str]) -> list[str]:
        if v is None:
            return []
        if len(v) not in {0, 5}:
            raise ValueError("derived_numbers must contain exactly 5 items")
        for s in v:
            if not isinstance(s, str):
                raise ValueError("derived_numbers must be strings")
            if len(s) != 4 or not s.isdigit():
                raise ValueError("derived_numbers items must be 4-digit zero-padded strings")
        return v


@dataclass(frozen=True)
class ScraperConfig:
    base_url: str = "https://www.resultadofacil.com.br"
    results_path: str = "/resultados-loteria-tradicional-de-hoje"
    headless: bool = True
    debug: bool = False
    navigation_timeout_ms: int = 60000
    action_timeout_ms: int = 30000
    viewport_width: int = 1366
    viewport_height: int = 768
    locale: str = "pt-BR"
    timezone_id: str = "America/Sao_Paulo"


class UserAgentRotator:
    def __init__(self, user_agents: Optional[list[str]] = None) -> None:
        self._user_agents = user_agents or [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]

    def pick(self) -> str:
        return random.choice(self._user_agents)


class HumanDelays:
    def __init__(self, min_s: float = 0.35, max_s: float = 1.6) -> None:
        self._min_s = min_s
        self._max_s = max_s

    async def jitter(self, factor: float = 1.0) -> None:
        delay = random.uniform(self._min_s, self._max_s) * factor
        await asyncio.sleep(delay)


class ResourceBlocker:
    def __init__(self, block_types: Optional[set[str]] = None) -> None:
        self._block_types = block_types or {"image", "media", "font"}

    async def route_handler(self, route: Route) -> None:
        try:
            if route.request.resource_type in self._block_types:
                await route.abort()
                return
            await route.continue_()
        except Exception as e:
            logger.debug("route_handler error: %s", e)
            try:
                await route.continue_()
            except Exception:
                return


class WafDetector:
    @staticmethod
    def looks_like_cloudflare(page_content: str, headers: dict[str, str]) -> bool:
        h = {k.lower(): v for k, v in headers.items()}
        if "cf-ray" in h or "cf-cache-status" in h:
            return True
        if "server" in h and "cloudflare" in h["server"].lower():
            return True
        if "attention required" in page_content.lower() and "cloudflare" in page_content.lower():
            return True
        if "/cdn-cgi/" in page_content.lower():
            return True
        return False

    @staticmethod
    def looks_blocked_status(status: Optional[int]) -> bool:
        return status in {401, 403, 406, 409, 412, 429, 503}


class LotonacionalScraper:
    def __init__(self, config: ScraperConfig) -> None:
        self._config = config
        self._ua_rotator = UserAgentRotator()
        self._delays = HumanDelays()
        self._resource_blocker = ResourceBlocker()

    async def run(self) -> list[LotteryDraw]:
        ua = self._ua_rotator.pick()
        if self._config.debug:
            logger.info("Using User-Agent: %s", ua)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._config.headless)
            try:
                context = await self._new_context(browser, ua)
                page = await context.new_page()
                await self._attach_debug_listeners(page)

                if stealth_async is not None:
                    await stealth_async(page)
                else:
                    logger.warning("playwright-stealth not installed; running without stealth patches")

                draws = await self._scrape_results(page)
                await context.close()
                return draws
            finally:
                await browser.close()

    async def _new_context(self, browser: Browser, user_agent: str) -> BrowserContext:
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": self._config.viewport_width, "height": self._config.viewport_height},
            locale=self._config.locale,
            timezone_id=self._config.timezone_id,
        )
        context.set_default_navigation_timeout(self._config.navigation_timeout_ms)
        context.set_default_timeout(self._config.action_timeout_ms)
        await context.route("**/*", self._resource_blocker.route_handler)
        return context

    async def _attach_debug_listeners(self, page: Page) -> None:
        if not self._config.debug:
            return

        page.on("console", lambda msg: logger.info("[console.%s] %s", msg.type, msg.text))
        page.on("pageerror", lambda err: logger.error("[pageerror] %s", err))
        page.on("requestfailed", lambda req: logger.warning("[requestfailed] %s %s", req.method, req.url))
        page.on("response", lambda resp: logger.debug("[response] %s %s", resp.status, resp.url))

    async def _scrape_results(self, page: Page) -> list[LotteryDraw]:
        url = f"{self._config.base_url}{self._config.results_path}"
        logger.info("Navigating to %s", url)

        await self._delays.jitter(1.2)
        response = await page.goto(url, wait_until="domcontentloaded")

        status = response.status if response else None
        headers = response.headers if response else {}
        logger.info("Navigation status=%s", status)

        await self._delays.jitter(0.8)

        content = await page.content()
        if WafDetector.looks_blocked_status(status) or WafDetector.looks_like_cloudflare(content, headers):
            await self._handle_possible_waf(page, status, headers)

        try:
            await self._wait_for_results_ready(page)
            draw_id, draw_date, numbers = await self._extract_results_precise(page)
        except TimeoutError:
            await self._dump_debug_html(page)
            raise
        except Exception:
            await self._dump_debug_html(page)
            raise
        draw = LotteryDraw(
            source_url=url,
            extracted_at_utc=datetime.utcnow(),
            draw_id=draw_id,
            draw_date=draw_date,
            numbers=numbers,
            derived_numbers=self._derive_complements(numbers),
        )
        return [draw]

    def _derive_complements(self, numbers: list[int]) -> list[str]:
        # Derivation rule: complement of 9999 (derived = 9999 - original), zero-padded to 4 digits.
        return [f"{(9999 - n):04d}" for n in numbers]

    async def _handle_possible_waf(self, page: Page, status: Optional[int], headers: dict[str, str]) -> None:
        logger.warning("Possible WAF/anti-bot detected (status=%s). Waiting for challenge to resolve.", status)

        if self._config.debug:
            logger.info("Response headers (subset): %s", {k: headers.get(k) for k in headers.keys() if k.lower().startswith("cf-") or k.lower() == "server"})

        await self._delays.jitter(2.5)

        try:
            await page.wait_for_function(
                "() => !document.location.pathname.startsWith('/cdn-cgi/')",
                timeout=45000,
            )
        except Exception:
            pass

        await self._delays.jitter(1.8)

    async def _wait_for_results_ready(self, page: Page) -> None:
        candidates = [
            "css=table",
            "css=table tr",
            "css=table tr:nth-child(2) td:nth-child(2)",
        ]

        last_err: Optional[Exception] = None
        for sel in candidates:
            try:
                await page.wait_for_selector(sel, timeout=20000)
                return
            except Exception as e:
                last_err = e

        logger.error("Results readiness check failed; page title=%s url=%s", await page.title(), page.url)
        if last_err:
            raise last_err

    async def _dump_debug_html(self, page: Page) -> None:
        try:
            html = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.error("Saved debug HTML to debug_page.html (url=%s title=%s)", page.url, await page.title())
        except Exception as e:
            logger.error("Failed to write debug_page.html: %s", e)

    async def _extract_results_precise(self, page: Page) -> tuple[str, str, list[int]]:
        """Extract 'Loteria Tradicional' results from ResultadoFacil.

        Observed structure (server-side render, no WAF challenge required):
        - A single table with header: Prêmio | Milhar | Grupo
        - Rows for 1º..5º with milhar values (4 digits) and group (2 digits)
        """

        await page.wait_for_selector("css=table", timeout=20000)

        h2 = await page.text_content("css=h2")
        h3 = await page.text_content("css=h3")
        draw_id = (h3 or "").strip()
        draw_date = (h2 or "").strip()

        rows = await page.query_selector_all("css=table tr")
        if len(rows) < 6:
            raise RuntimeError(f"Unexpected table shape: {len(rows)} rows")

        numbers: list[int] = []
        for tr in rows[1:6]:
            tds = await tr.query_selector_all("css=td")
            if len(tds) < 2:
                continue
            milhar_raw = ((await tds[1].inner_text()) or "").strip()
            milhar_digits = "".join(ch for ch in milhar_raw if ch.isdigit())
            if not milhar_digits:
                raise RuntimeError(f"Non-numeric milhar: {milhar_raw}")
            numbers.append(int(milhar_digits))

        if len(numbers) != 5:
            raise RuntimeError(f"Expected 5 milhar numbers, got {len(numbers)}")

        logger.info("Extracted ResultadoFacil Loteria Tradicional numbers=%s", ",".join(str(n) for n in numbers))
        return draw_id, draw_date, numbers


def _configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


async def main() -> None:
    config = ScraperConfig(
        headless=False,
        debug=True,
    )
    _configure_logging(config.debug)

    scraper = LotonacionalScraper(config)
    try:
        draws = await scraper.run()
        if len(draws) == 1:
            print(draws[0].model_dump_json(indent=2))
        else:
            print(json.dumps([d.model_dump(mode="json") for d in draws], ensure_ascii=False, indent=2))
    except ValidationError as e:
        logger.error("Validation error: %s", e)
        return
    except TimeoutError as e:
        logger.error("Timeout waiting for page readiness: %s", e)
        return
    except Exception as e:
        logger.exception("Scrape failed: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
