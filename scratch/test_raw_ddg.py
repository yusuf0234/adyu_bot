import httpx, asyncio
from bs4 import BeautifulSoup

async def test_ddg_html():
    q = "hüseyin kutlu site:adiyaman.edu.tr"
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    data = {"q": q}
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=data, headers=headers)
        print("Status:", resp.status_code)
        
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", class_="result__url"):
            print(a.get("href"))

asyncio.run(test_ddg_html())
