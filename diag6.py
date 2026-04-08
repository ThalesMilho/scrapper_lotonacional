import asyncio, sys, httpx
sys.path.insert(0, '/app')
from scrapers.http_client import LotteryHttpClient
from bs4 import BeautifulSoup

URL = "https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje"

async def test():
    # --- Request A: plain httpx (known working) ---
    r1 = httpx.get(URL, follow_redirects=True)
    print(f"[plain httpx]")
    print(f"  Status: {r1.status_code}")
    print(f"  Content-length: {len(r1.text)}")
    print(f"  HTTP version: {r1.http_version}")
    print(f"  Request headers sent:")
    for k, v in r1.request.headers.items():
        print(f"    {k}: {v}")

    print()

    # --- Request B: LotteryHttpClient ---
    async with LotteryHttpClient() as client:
        r2 = await client.get(URL)
        print(f"[LotteryHttpClient]")
        print(f"  Status: {r2.status_code}")
        print(f"  Content-length: {len(r2.text)}")
        print(f"  HTTP version: {r2.http_version}")
        print(f"  Request headers sent:")
        for k, v in r2.request.headers.items():
            print(f"    {k}: {v}")

asyncio.run(test())
