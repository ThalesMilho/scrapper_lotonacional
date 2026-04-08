import sys, logging
sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

import httpx
from scrapers.resultado_facil_scraper import ResultadoFacilScraper
from scrapers.http_client import LotteryHttpClient
from models.schemas import SourceID

r = httpx.get(
    "https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
    follow_redirects=True,
)

# Build instance exactly as orchestrator would
client  = LotteryHttpClient()
scraper = ResultadoFacilScraper(
    client=client,
    source_id=SourceID.BOA_SORTE,
    url="https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
    state="GO",
)

# Call parse_html and capture warnings
import logging
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.WARNING)
logging.getLogger().addHandler(handler)

sessions = scraper.parse_html(r.text)
print(f"\n=== parse_html returned {len(sessions)} sessions ===")
for s in sessions:
    print(f"  {s.session_id} | {s.draw_time} | entries={len(s.entries)}")
