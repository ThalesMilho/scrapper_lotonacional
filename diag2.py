import sys, traceback, re, inspect
sys.path.insert(0, '/app')
import httpx
from bs4 import BeautifulSoup

r = httpx.get("https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje", follow_redirects=True)
soup = BeautifulSoup(r.text, "lxml")

from scrapers.resultado_facil_scraper import ResultadoFacilScraper
inst = object.__new__(ResultadoFacilScraper)

# ── 1. Date/time extraction ──────────────────────────────────────────────
print("=== _extract_date_from_heading / _extract_time_from_heading ===")
labels = [
    "BOA SORTE - GOIÁS, 09h - Resultado do dia 05/04/2026 (Domingo)",
    "BOA SORTE - GOIÁS, 11h - Resultado do dia 05/04/2026 (Domingo)",
]
for label in labels:
    try:
        d = inst._extract_date_from_heading(label)
        t = inst._extract_time_from_heading(label)
        print(f"  label: {label[:50]}")
        print(f"    date={d!r}  time={t!r}")
    except Exception as e:
        print(f"  RAISED: {e}")
        traceback.print_exc()

# ── 2. DrawSession construction ─────────────────────────────────────────
print("\n=== DrawSession construction ===")
from models.schemas import DrawSession, DrawEntry, SourceID
entries = [
    DrawEntry(premio=1, milhar='5106', centena='106', dezena='06', grupo=2, bicho='Águia'),
    DrawEntry(premio=2, milhar='9923', centena='923', dezena='23', grupo=6, bicho='Cabra'),
]
label = "BOA SORTE - GOIÁS, 09h - Resultado do dia 05/04/2026 (Domingo)"
draw_date = inst._extract_date_from_heading(label)
draw_time = inst._extract_time_from_heading(label)
print(f"  draw_date={draw_date!r}  draw_time={draw_time!r}")

# Try every plausible SourceID value
for sid in list(SourceID):
    try:
        s = DrawSession(
            source_id=sid,
            source_url="https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
            draw_date=draw_date,
            draw_time=draw_time,
            draw_label=label,
            state="GO",
            banca=None,
            entries=entries,
        )
        print(f"  DrawSession OK with source_id={sid!r}: session_id={s.session_id!r}")
        break
    except Exception as e:
        print(f"  DrawSession FAILED source_id={sid!r}: {e}")

# ── 3. Show parse_html source (session-building loop only) ───────────────
print("\n=== parse_html / scrape source ===")
for method_name in ("parse_html", "scrape", "_parse", "parse"):
    m = getattr(inst, method_name, None)
    if m:
        src = inspect.getsource(m)
        print(f"--- {method_name} ---")
        print(src)
        break

# ── 4. Show _extract methods source ─────────────────────────────────────
print("\n=== _extract_date / _extract_time source ===")
for method_name in ("_extract_date_from_heading", "_extract_time_from_heading"):
    m = getattr(inst, method_name, None)
    if m:
        print(f"--- {method_name} ---")
        print(inspect.getsource(m))

# ── 5. Show SourceID enum values ─────────────────────────────────────────
print("\n=== SourceID values ===")
print(inspect.getsource(SourceID))
