import httpx, asyncio
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

async def test_ask():
    q = "hüseyin kutlu site:adiyaman.edu.tr"
    url = f"https://www.ask.com/web?q={quote_plus(q)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        print("Status:", resp.status_code)
        
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "adiyaman.edu.tr" in href:
                if href not in links:
                    links.append(href)
        
        print("Ask found links:", len(links))
        for l in links[:5]:
            print(l)

asyncio.run(test_ask())
