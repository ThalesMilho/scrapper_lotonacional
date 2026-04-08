import asyncio, sys
sys.path.insert(0, '/app')
from scrapers.http_client import LotteryHttpClient
from scrapers.resultado_facil_scraper import ResultadoFacilScraper
from models.schemas import SourceID
from bs4 import BeautifulSoup

async def test():
    async with LotteryHttpClient() as client:
        r = await client.get("https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje")
        print(f"Status: {r.status_code}")
        print(f"Content-length: {len(r.text)}")
        print(f"Encoding: {r.encoding}")

        soup = BeautifulSoup(r.text, "lxml")
        h3s = soup.find_all("h3", class_="h4")
        print(f"h3.h4 headings found: {len(h3s)}")
        for h in h3s[:2]:
            print(f"  {h.get_text(strip=True)[:70]}")

        scraper = ResultadoFacilScraper(
            client=client,
            source_id=SourceID.BOA_SORTE,
            url="https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
            state="GO",
        )
        sessions = scraper.parse_html(r.text)
        print(f"\nparse_html with LotteryHttpClient response: {len(sessions)} sessions")

asyncio.run(test())
