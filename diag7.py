import asyncio, sys, httpx
sys.path.insert(0, '/app')
from bs4 import BeautifulSoup

URL = "https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje"

# Test minimal headers only - replicate exactly what plain httpx sends
async def test():
    async with httpx.AsyncClient(
        headers={},   # no custom headers at all
        follow_redirects=True,
        http2=False,
    ) as client:
        r = await client.get(URL)
        print(f"AsyncClient bare")
        print(f"  Content-length: {len(r.text)}")
        print(f"  HTTP version: {r.http_version}")
        soup = BeautifulSoup(r.text, "lxml")
        print(f"  h3.h4 headings: {len(soup.find_all('h3', class_='h4'))}")

asyncio.run(test())
