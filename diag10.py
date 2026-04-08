import sys, httpx, re
sys.path.insert(0, '/app')
from bs4 import BeautifulSoup
from scrapers.resultado_facil_scraper import ResultadoFacilScraper
from scrapers.http_client import LotteryHttpClient
from models.schemas import SourceID

r = httpx.get("https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/rj", follow_redirects=True)
soup = BeautifulSoup(r.text, "lxml")

# Show what headings the scraper now finds and what label it extracts
headings = []
_seen = set()
for _tag in soup.find_all(["h3", "h4"]) + soup.find_all(class_=re.compile(r"^h[34]$")) + soup.find_all("h3", class_="g"):
    if id(_tag) not in _seen:
        _seen.add(id(_tag))
        headings.append(_tag)

print(f"Total headings found: {len(headings)}")
for h in headings[:15]:
    label = h.get_text(strip=True)
    print(f"  [{h.name} class={h.get('class')}] {label[:70]}")
