import sys, traceback, re
sys.path.insert(0, '/app')

import httpx
from bs4 import BeautifulSoup

r = httpx.get(
    "https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
    follow_redirects=True,
)
soup = BeautifulSoup(r.text, "lxml")

# ── 1. _clean() output ────────────────────────────────────────────────────
try:
    from scrapers.resultado_facil_scraper import ResultadoFacilScraper
    inst = object.__new__(ResultadoFacilScraper)
    print("=== _clean() output ===")
    for s in ["1º", "5106", "02", "Águia", "6º [soma]", "8326", "", "7º [mult]"]:
        print(f"  clean({s!r}) -> {inst._clean(s)!r}")
except Exception as e:
    print(f"IMPORT/_clean FAILED: {e}")
    traceback.print_exc()

# ── 2. _next_table() ──────────────────────────────────────────────────────
print("\n=== _next_table() output ===")
h3 = soup.find("h3", class_="h4")
try:
    table = inst._next_table(h3)
    print(f"  returned: {table is not None}")
    if table:
        print(f"  rows: {len(table.find_all('tr'))}")
    else:
        # show what siblings exist between h3 and next table
        sib = h3.find_next_sibling()
        while sib:
            print(f"  sibling: <{sib.name} class={sib.get('class')}> → is table: {sib.name=='table'}")
            if sib.name == "table":
                break
            sib = sib.find_next_sibling()
except Exception as e:
    print(f"  RAISED: {e}")
    traceback.print_exc()

# ── 3. _parse_table() ────────────────────────────────────────────────────
print("\n=== _parse_table() output ===")
table = h3.find_next_sibling("table")
print(f"  find_next_sibling('table'): {table is not None}")
try:
    entries = inst._parse_table(table)
    print(f"  returned {len(entries)} entries")
    for e in entries:
        print(f"    {e}")
except Exception as e:
    print(f"  RAISED: {e}")
    traceback.print_exc()

# ── 4. Row-by-row with full exception detail ─────────────────────────────
print("\n=== Row-by-row manual parse ===")
from models.schemas import DrawEntry
SKIP_RE = re.compile(r"\[(soma|mult)\]", re.I)
for i, row in enumerate(table.find_all("tr")):
    tds = row.find_all("td")
    if not tds:
        print(f"  row[{i}]: no <td> (header row)")
        continue
    cols = [td.get_text(strip=True) for td in tds]
    if SKIP_RE.search(cols[0]):
        print(f"  row[{i}]: derived skip {cols[:2]}")
        continue
    try:
        premio_str = re.sub(r"[^\d]", "", cols[0])
        grupo_str  = re.sub(r"[^\d]", "", cols[2]) if len(cols) > 2 else ""
        milhar     = cols[1].zfill(4) if len(cols) > 1 else ""
        e = DrawEntry(
            premio=int(premio_str), milhar=milhar,
            centena=milhar[-3:], dezena=milhar[-2:],
            grupo=int(grupo_str) if grupo_str else 0,
            bicho=cols[3] if len(cols) > 3 else "",
        )
        print(f"  row[{i}]: OK → {e}")
    except Exception as ex:
        print(f"  row[{i}]: FAILED cols={cols} → {ex}")

# ── 5. _parse_table source ───────────────────────────────────────────────
print("\n=== _parse_table source ===")
import inspect
try:
    print(inspect.getsource(inst._parse_table))
except Exception as e:
    print(f"  could not get source: {e}")

# ── 6. Nacional JS-render check ──────────────────────────────────────────
print("\n=== Nacional page check ===")
rn   = httpx.get("https://www.lotonacional.com.br/loteria-federal/resultados/", follow_redirects=True)
sn   = BeautifulSoup(rn.text, "lxml")
print(f"  Tables in HTML: {len(sn.find_all('table'))}")
for script in sn.find_all("script"):
    txt = script.string or ""
    if any(kw in txt.lower() for kw in ["milhar", "premio", "resultado", "sorteio"]):
        print(f"  Inline data script found (first 300 chars): {txt[:300]!r}")
        break
else:
    print("  No inline result data → page is CSR (needs Playwright)")
