import asyncio
import argparse
import json
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from playwright.async_api import Browser, BrowserContext, Page, Route, async_playwright

try:
    from playwright_stealth import stealth_async
except Exception:  # pragma: no cover
    stealth_async = None


logger = logging.getLogger("bicho_scraper")


FOUR_DIGIT_NUMBER_RE = re.compile(r"^\d{4}$")


@dataclass(frozen=True)
class Source:
    key: str
    url: str


ALL_SOURCES: list[Source] = [
    Source("SRC_NACIONAL", "https://www.resultadofacil.com.br/resultados-loteria-nacional-de-hoje"),
    Source("SRC_RJ", "https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/RJ"),
    Source("SRC_SP", "https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/SP"),
    Source("SRC_GO", "https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/GO"),
    Source("SRC_BA", "https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/BA"),
    Source("SRC_MG", "https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/MG"),
    Source("SRC_LOTEP", "http://resultadofacil.com.br/resultados-lotep-de-hoje"),
    Source("SRC_FEDERAL", "https://www.resultadofacil.com.br/ultimos-resultados-da-federal"),
]


EXPECTED_TIMES: dict[str, set[str]] = {
    "LT_NACIONAL": {"02:00", "08:00", "10:00", "12:00"},
    "LT_LOOK": {"07:00", "09:00", "11:00"},
    "PT_SP": {"08:00", "10:00", "12:00"},
    "LT_PT_RIO": {"09:00", "11:00"},
    "LT_BOASORTE": {"09:00", "11:00"},
    "LT_LOTEP": {"09:00", "10:00", "12:00"},
    "LT_BAHIA": {"10:00", "12:00"},
    "LT_MINAS_SALV": {"13:00"},
    "LT_FEDERAL": set(),
}


LOTTERY_MAP: list[tuple[str, str]] = [
    ("MINAS SALVADOR", "LT_MINAS_SALV"),
    ("MINAS SALV", "LT_MINAS_SALV"),
    ("BOASORTE", "LT_BOASORTE"),
    ("BOA SORTE", "LT_BOASORTE"),
    ("PT RIO", "LT_PT_RIO"),
    ("NACIONAL", "LT_NACIONAL"),
    ("LOTEP", "LT_LOTEP"),
    ("BAHIA", "LT_BAHIA"),
    ("LOOK", "LT_LOOK"),
    ("PT SP", "PT_SP"),
    ("PT/SP", "PT_SP"),
    ("FEDERAL", "LT_FEDERAL"),
]


ANIMAL_TABLE: dict[int, str] = {
    1: "Avestruz",
    2: "Águia",
    3: "Burro",
    4: "Borboleta",
    5: "Cachorro",
    6: "Cabra",
    7: "Carneiro",
    8: "Camelo",
    9: "Cobra",
    10: "Coelho",
    11: "Cavalo",
    12: "Elefante",
    13: "Galo",
    14: "Gato",
    15: "Jacaré",
    16: "Leão",
    17: "Macaco",
    18: "Porco",
    19: "Pavão",
    20: "Peru",
    21: "Touro",
    22: "Tigre",
    23: "Urso",
    24: "Veado",
    25: "Vaca",
}


CANDIDATE_SELECTORS: list[str] = [
    ".resultado-sorteio",
    ".bloco-resultado",
    ".sorteio-container",
    "table.resultados",
    "[class*='resultado']",
    "[class*='sorteio']",
]


BLOCK_HEADER_PATTERN = re.compile(
    r"Nacional\s*-\s*LN\s+(\d{2}:\d{2})\s*-\s*Resultado do dia\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

TIME_PATTERN = re.compile(r"(\d{2})HS", re.IGNORECASE)

RESULT_LINE_PATTERN = re.compile(
    r"(\d{1,2})º\s+(\d{4})\s+(\d{1,2})\s+([A-Za-zÀ-úãõàâêôç]+)",
    re.IGNORECASE | re.UNICODE,
)


SKIP_LINE_PATTERNS = ["[soma]", "prêmio", "premio", "milhar", "grupo", "bicho"]


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


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def detect_variant(header: str) -> str:
    return "MALUCA" if "MALUCA" in (header or "").upper() else "NORMAL"


def extract_time(header: str) -> tuple[Optional[str], Optional[str]]:
    # Try HH:MM format first (e.g., "02:00")
    match = re.search(r"(\d{2}:\d{2})", header or "")
    if match:
        time_norm = match.group(1)
        return time_norm, time_norm
    # Fallback to HS format (e.g., "09HS")
    match = TIME_PATTERN.search(header or "")
    if match:
        hour = match.group(1)
        time_norm = f"{hour}:00"
        time_raw = f"{hour}HS"
        return time_norm, time_raw
    return None, None


def match_lottery(header: str) -> str:
    clean = (header or "").upper()
    for substring, key in LOTTERY_MAP:
        if substring in clean:
            return key
    return "UNKNOWN"


def validate_animal(group_id: int, scraped_animal: str) -> bool:
    expected = ANIMAL_TABLE.get(group_id, "")
    return expected.strip().lower() == (scraped_animal or "").strip().lower()


def compute_fields(number: str) -> dict[str, str]:
    n = normalize_number(number)
    A, B, C, D = n[0], n[1], n[2], n[3]
    return {
        "number": n,
        "milhar": n,
        "milhar_inv": D + C + B + A,
        "centena": B + C + D,
        "centena_esq": A + B + C,
        "centena_inv": D + C + B,
        "centena_inv_esq": C + B + A,
        "dezena": C + D,
        "unidade": D,
    }


def normalize_number(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) > 4:
        digits = digits[-4:]
    candidate = digits.zfill(4)
    if not FOUR_DIGIT_NUMBER_RE.fullmatch(candidate):
        raise ValueError(f"Invalid 4-digit number: {value!r}")
    return candidate


def compute_modalities(results: list[dict[str, Any]]) -> dict[str, Any]:
    r = {item.get("pos"): item for item in results if isinstance(item.get("pos"), int)}

    def gp(n: int) -> int:
        return int(r[n]["group_id"])

    def dz(n: int) -> str:
        return str(r[n]["dezena"])

    def ct(n: int) -> str:
        return str(r[n]["centena"])

    def cesq(n: int) -> str:
        return str(r[n]["centena_esq"])

    if 1 not in r:
        return {
            "CENTENA": None,
            "CENTENA_INV": None,
            "CENTENA_INV_ESQ": None,
            "CENTENA_ESQ": None,
            "MILHAR": None,
            "MILHAR_CT": None,
            "MILHAR_INV": None,
            "UNIDADE": None,
            "DEZENA": None,
            "DUQUE_DEZ": None,
            "TERNO_DEZ": None,
            "SECO_TERNO_DEZ": None,
            "GRUPO": None,
            "DUQUE_GP": None,
            "TERNO_GP": None,
            "QUADRA_GP": None,
            "QUINA_GP": None,
            "QUINA_GP_ESQ": None,
            "QUINA_GP_MEIO": None,
            "SENA_GP": None,
            "SENA_GP_ESQ": None,
            "SENA_GP_MEIO": None,
            "PASSE_VAI": None,
            "PASSE_VAI_VEM": None,
            "PALPITAO": None,
        }

    terno_dez = None
    seco = None
    if all(k in r for k in (1, 2, 3)):
        terno_dez = [dz(1), dz(2), dz(3)]
        seco = terno_dez if len(set(terno_dez)) == 3 else None

    duque_dez = [dz(1), dz(2)] if all(k in r for k in (1, 2)) else None
    duque_gp = [gp(1), gp(2)] if all(k in r for k in (1, 2)) else None
    terno_gp = [gp(1), gp(2), gp(3)] if all(k in r for k in (1, 2, 3)) else None

    quadra_gp = [gp(i) for i in range(1, 5)] if all(k in r for k in (1, 2, 3, 4)) else None
    quina_gp = [gp(i) for i in range(1, 6)] if all(k in r for k in (1, 2, 3, 4, 5)) else None
    quina_gp_esq = [cesq(i) for i in range(1, 6)] if quina_gp is not None else None
    quina_gp_meio = [ct(i) for i in range(1, 6)] if quina_gp is not None else None

    sena_gp = [gp(i) for i in range(1, 7)] if all(k in r for k in (1, 2, 3, 4, 5, 6)) else None
    sena_gp_esq = [cesq(i) for i in range(1, 7)] if sena_gp is not None else None
    sena_gp_meio = [ct(i) for i in range(1, 7)] if sena_gp is not None else None

    return {
        "CENTENA": r[1].get("centena"),
        "CENTENA_INV": r[1].get("centena_inv"),
        "CENTENA_INV_ESQ": r[1].get("centena_inv_esq"),
        "CENTENA_ESQ": r[1].get("centena_esq"),
        "MILHAR": r[1].get("milhar"),
        "MILHAR_CT": [r[1].get("milhar"), r[1].get("centena")],
        "MILHAR_INV": r[1].get("milhar_inv"),
        "UNIDADE": r[1].get("unidade"),
        "DEZENA": dz(1),
        "DUQUE_DEZ": duque_dez,
        "TERNO_DEZ": terno_dez,
        "SECO_TERNO_DEZ": seco,
        "GRUPO": {"group_id": gp(1), "animal": r[1].get("animal")},
        "DUQUE_GP": duque_gp,
        "TERNO_GP": terno_gp,
        "QUADRA_GP": quadra_gp,
        "QUINA_GP": quina_gp,
        "QUINA_GP_ESQ": quina_gp_esq,
        "QUINA_GP_MEIO": quina_gp_meio,
        "SENA_GP": sena_gp,
        "SENA_GP_ESQ": sena_gp_esq,
        "SENA_GP_MEIO": sena_gp_meio,
        "PASSE_VAI": None,
        "PASSE_VAI_VEM": None,
        "PALPITAO": {
            "milhar": r[1].get("milhar"),
            "centena": r[1].get("centena"),
            "dezena": dz(1),
            "grupo": gp(1),
            "duque_gp": duque_gp,
        },
    }


def _http_headers() -> dict[str, str]:
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://www.resultadofacil.com.br/",
    }


def _today_br() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def _find_source_or_raise(source_key: str) -> Source:
    for src in ALL_SOURCES:
        if src.key.upper() == (source_key or "").strip().upper():
            return src
    raise ValueError(f"Unknown source key: {source_key}. Valid keys: {', '.join(s.key for s in ALL_SOURCES)}")


def _find_blocks_by_dom(page: Page) -> list[str]:
    # DOM-first: return list of block texts
    return []


async def debug_raw(source_key: str) -> None:
    _configure_logging()

    src = _find_source_or_raise(source_key)
    warnings: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await _new_context_async(browser)
            page = await context.new_page()

            if stealth_async is not None:
                try:
                    await stealth_async(page)
                except Exception:
                    pass

            # Reuse the same load/wait strategy but print raw body text and exit.
            for attempt in range(1, 4):
                try:
                    logger.info("[debug-raw] Loading %s (%s) attempt=%s", src.key, src.url, attempt)
                    await page.goto(src.url, wait_until="domcontentloaded", timeout=45000)
                    try:
                        await page.wait_for_selector(".resultado, .sorteio, table", timeout=15000)
                    except Exception:
                        pass
                    body_text = await page.inner_text("body")
                    print(body_text)
                    break
                except Exception as e:
                    if attempt == 3:
                        msg = f"[debug-raw] Failed to load {src.url} after 3 attempts: {e}"
                        logger.warning(msg)
                        warnings.append(msg)
                    else:
                        await asyncio.sleep(1.25 * attempt)

            await context.close()
        finally:
            await browser.close()


def _split_blocks_by_regex(full_text: str) -> list[str]:
    # Split the page into blocks, each starting with a header like "Nacional - LN 02:00 - Resultado do dia ..."
    if not full_text:
        return []
    # Find all header positions
    header_positions = []
    for m in BLOCK_HEADER_PATTERN.finditer(full_text):
        header_positions.append(m.start())
    if not header_positions:
        # Fallback: try generic pattern
        for m in BLOCK_HEADER_GENERIC_PATTERN.finditer(full_text):
            header_positions.append(m.start())
    if not header_positions:
        return []
    # Slice blocks between headers (from each header to before the next header)
    blocks = []
    for i, start in enumerate(header_positions):
        end = header_positions[i + 1] if i + 1 < len(header_positions) else len(full_text)
        blocks.append(full_text[start:end].strip())
    return blocks


def _parse_results(block_text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    text = block_text or ""
    lower = text.lower()
    for s in SKIP_LINE_PATTERNS:
        # Skip patterns are checked per-line below; this early check just avoids work if page is empty.
        if s in lower:
            break

    for line in text.splitlines():
        ln = (line or "").strip()
        if not ln:
            continue
        lnl = ln.lower()
        if any(pat in lnl for pat in SKIP_LINE_PATTERNS):
            continue

        m = RESULT_LINE_PATTERN.search(ln)
        if not m:
            continue

        pos = int(m.group(1))
        number = normalize_number(m.group(2) or "")
        group_id = int(m.group(3))
        animal = (m.group(4) or "").strip()

        fields = compute_fields(number)
        mismatch = not validate_animal(group_id, animal)

        results.append(
            {
                "pos": pos,
                "number": fields["number"],
                "group_id": group_id,
                "animal": animal,
                "animal_mismatch": mismatch,
                "milhar": fields["milhar"],
                "milhar_inv": fields["milhar_inv"],
                "centena": fields["centena"],
                "centena_esq": fields["centena_esq"],
                "centena_inv": fields["centena_inv"],
                "centena_inv_esq": fields["centena_inv_esq"],
                "dezena": fields["dezena"],
                "unidade": fields["unidade"],
            }
        )

    # Preserve insertion order; also keep only first occurrence of each pos if duplicates
    seen: set[int] = set()
    deduped: list[dict[str, Any]] = []
    for item in results:
        p = item.get("pos")
        if not isinstance(p, int):
            continue
        if p in seen:
            continue
        seen.add(p)
        deduped.append(item)
    return deduped


def _parse_draw(block_text: str, source_key: str, date_br: str) -> dict[str, Any]:
    header_line = (block_text or "").strip().splitlines()[0] if block_text else ""
    variant = detect_variant(header_line)
    time_norm, time_raw = extract_time(header_line)
    lottery = match_lottery(header_line)

    print(f"[DEBUG] _parse_draw: header_line={header_line!r}, time_norm={time_norm}, time_raw={time_raw}, lottery={lottery}")

    unknown_lottery = lottery == "UNKNOWN"

    results = _parse_results(block_text)
    incomplete = len(results) < 10

    expected = EXPECTED_TIMES.get(lottery)
    unexpected_time = False
    if expected is not None and len(expected) > 0 and time_norm is not None:
        unexpected_time = time_norm not in expected

    modalities = compute_modalities(results)

    draw = {
        "source": source_key,
        "lottery": lottery,
        "variant": variant,
        "time": time_norm,
        "time_raw": time_raw,
        "date": date_br,
        "unexpected_time": bool(unexpected_time),
        "incomplete": bool(incomplete),
        "missing_normal_pair": False,
        "duplicate": False,
        "unknown_lottery": bool(unknown_lottery),
        "passe_pending": False,
        "results": results,
        "modalities": modalities,
    }
    print(f"[DEBUG] _parse_draw returning draw with time={time_norm}, results={len(results)}")
    return draw


def compute_missing_pairs_and_duplicates(draws: list[dict[str, Any]]) -> None:
    # duplicates: same (source, lottery, variant, time) appears multiple times
    seen: set[tuple[Any, Any, Any, Any]] = set()
    for d in draws:
        key = (d.get("source"), d.get("lottery"), d.get("variant"), d.get("time"))
        if key in seen:
            d["duplicate"] = True
        else:
            seen.add(key)

    # missing_normal_pair: if MALUCA exists but NORMAL does not for same lottery+time
    normals: set[tuple[Any, Any]] = set()
    malucas: list[dict[str, Any]] = []
    for d in draws:
        lt = d.get("lottery")
        tm = d.get("time")
        if d.get("variant") == "NORMAL":
            normals.add((lt, tm))
        elif d.get("variant") == "MALUCA":
            malucas.append(d)

    for d in malucas:
        if (d.get("lottery"), d.get("time")) not in normals:
            d["missing_normal_pair"] = True


def compute_passe(draws: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for d in draws:
        lottery = d.get("lottery")
        variant = d.get("variant")
        if not lottery or not variant:
            continue
        groups.setdefault((str(lottery), str(variant)), []).append(d)

    for _, ds in groups.items():
        ds.sort(key=lambda x: (x.get("time") or "99:99"))
        for i, d in enumerate(ds):
            next_d = ds[i + 1] if i + 1 < len(ds) else None
            if next_d is None:
                d["passe_pending"] = True
                continue

            if not d.get("results") or not next_d.get("results"):
                d["passe_pending"] = True
                continue

            this_gp = d["results"][0].get("group_id")
            next_gp = next_d["results"][0].get("group_id")
            if isinstance(this_gp, int) and isinstance(next_gp, int):
                d["modalities"]["PASSE_VAI"] = next_gp
                d["modalities"]["PASSE_VAI_VEM"] = this_gp == next_gp
                d["passe_pending"] = False
            else:
                d["passe_pending"] = True


def _pick_block_texts(page: Page, body_text: str) -> list[str]:
    # DOM strategy not implemented yet; use regex fallback always.
    return _split_blocks_by_regex(body_text)


def _ensure_page_ready(page: Page) -> None:
    # placeholder for sync signature; actual waiting done in async function
    return None


def _build_output(date_br: str, draws: list[dict[str, Any]], sources_loaded: list[str], sources_failed: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "_meta": {
            "date": date_br,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "total_draws_found": len(draws),
            "sources_loaded": sources_loaded,
            "sources_failed": sources_failed,
            "warnings": warnings,
        },
        "draws": draws,
    }


def _new_context(browser: Browser) -> BrowserContext:
    raise RuntimeError("_new_context must be called from async context")


async def _new_context_async(browser: Browser) -> BrowserContext:
    headers = _http_headers()
    context = await browser.new_context(
        user_agent=headers["User-Agent"],
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        viewport={"width": 1366, "height": 768},
        extra_http_headers=headers,
    )
    blocker = ResourceBlocker()
    await context.route("**/*", blocker.route_handler)
    return context


async def scrape_source(page: Page, source: Source, date_br: str, warnings: list[str]) -> list[dict[str, Any]]:
    for attempt in range(1, 4):
        try:
            logger.info("Loading %s (%s) attempt=%s", source.key, source.url, attempt)
            await page.goto(source.url, wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_selector(".resultado, .sorteio, table", timeout=15000)
            except Exception:
                pass

            body_text = await page.inner_text("body")
            blocks = _pick_block_texts(page, body_text)
            draws = [_parse_draw(b, source.key, date_br) for b in blocks]
            return [d for d in draws if d.get("time") is not None]
        except Exception as e:
            if attempt == 3:
                msg = f"Failed to load {source.url} after 3 attempts: {e}"
                logger.warning(msg)
                warnings.append(msg)
                return []
            await asyncio.sleep(1.25 * attempt)

    return []


async def run(output_file: Optional[str] = None, date_br: Optional[str] = None) -> dict[str, Any]:
    _configure_logging()

    date_str = date_br or _today_br()
    warnings: list[str] = []
    sources_loaded: list[str] = []
    sources_failed: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await _new_context_async(browser)
            page = await context.new_page()

            if stealth_async is not None:
                try:
                    await stealth_async(page)
                except Exception:
                    pass

            all_draws: list[dict[str, Any]] = []
            for src in ALL_SOURCES:
                draws = await scrape_source(page, src, date_str, warnings)
                if draws:
                    sources_loaded.append(src.key)
                else:
                    sources_failed.append(src.key)
                all_draws.extend(draws)

            compute_missing_pairs_and_duplicates(all_draws)
            compute_passe(all_draws)

            out = _build_output(
                date_br=date_str,
                draws=all_draws,
                sources_loaded=sources_loaded,
                sources_failed=sources_failed,
                warnings=warnings,
            )

            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
            else:
                print(json.dumps(out, ensure_ascii=False, indent=2))

            await context.close()
            return out
        finally:
            await browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jogo do Bicho scraper (resultadofacil.com.br)")
    parser.add_argument("--output", dest="output_file", default=None, help="Write JSON output to a file")
    parser.add_argument("--date", dest="date_br", default=None, help="Target date in DD/MM/YYYY (default: today)")
    parser.add_argument("--source", dest="source_key", default=None, help="Run only a single source (e.g. SRC_NACIONAL)")
    parser.add_argument(
        "--debug-raw",
        dest="debug_raw",
        default=None,
        metavar="SRC_KEY",
        help="Load only one source, print raw page inner_text(body), and exit",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.debug_raw:
        asyncio.run(debug_raw(args.debug_raw))
    else:
        if args.source_key:
            # Override global execution order to only one source.
            ALL_SOURCES[:] = [_find_source_or_raise(args.source_key)]
        asyncio.run(run(output_file=args.output_file, date_br=args.date_br))
