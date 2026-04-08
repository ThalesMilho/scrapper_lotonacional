import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    url = "https://www.lotonacional.com.br/loteria-federal/resultados/"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        html = await page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
