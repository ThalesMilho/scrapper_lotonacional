import asyncio, sys, httpx, json
sys.path.insert(0, '/app')
from scrapers.http_client import LotteryHttpClient
from scrapers.resultado_facil_scraper import ResultadoFacilScraper
from models.schemas import SourceID, WebhookPayload
from bs4 import BeautifulSoup
import os

URL = "https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
API_KEY = os.getenv("WEBHOOK_API_KEY", "")

async def test():
    async with LotteryHttpClient() as client:
        r = await client.get(URL)
        scraper = ResultadoFacilScraper(
            client=client,
            source_id=SourceID.BOA_SORTE,
            url=URL,
            state="GO",
        )
        sessions = scraper.parse_html(r.text)
        session = sessions[0]
        payload = WebhookPayload.from_session(session)
        print("=== Payload being sent ===")
        print(payload.model_dump_json(indent=2))

        print("\n=== API Response ===")
        async with httpx.AsyncClient() as hclient:
            resp = await hclient.post(
                WEBHOOK_URL,
                content=payload.model_dump_json(),
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            )
            print(f"HTTP {resp.status_code}")
            print(json.dumps(resp.json(), indent=2))

asyncio.run(test())
