import httpx, asyncio
from bs4 import BeautifulSoup

async def test_ddg_html_class():
    q = "hüseyin kutlu site:adiyaman.edu.tr"
    url = "https://html.duckduckgo.com/html/"
    data = {"q": q}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=data, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        found = soup.find_all("a", class_="result__url")
        print(f"Found {len(found)} links with class 'result__url'")

asyncio.run(test_ddg_html_class())
