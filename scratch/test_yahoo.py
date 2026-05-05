import httpx, asyncio
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, unquote

async def test_yahoo():
    q = "hüseyin kutlu site:adiyaman.edu.tr"
    url = f"https://search.yahoo.com/search?p={quote_plus(q)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        print("Status:", resp.status_code)
        
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "adiyaman.edu.tr" in href:
                # Yahoo wraps links in their own redirect, e.g. https://r.search.yahoo.com/.../RU=https://...
                if "RU=" in href:
                    href = unquote(href.split("RU=")[1].split("/RK=")[0])
                if href not in links:
                    links.append(href)
        print("Yahoo URLs:", links)

asyncio.run(test_yahoo())
