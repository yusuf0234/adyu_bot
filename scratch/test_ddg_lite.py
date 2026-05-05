import httpx, asyncio
from bs4 import BeautifulSoup

async def test_ddg_html():
    q = "hüseyin kutlu site:adiyaman.edu.tr"
    url = "https://html.duckduckgo.com/html/"
    data = {"q": q}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=data, headers=headers)
        print("Status:", resp.status_code)
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Let's find all links and see which ones are results
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "adiyaman.edu.tr" in href:
                links.append(href)
        
        print("Found links:", len(links))
        for l in links[:5]:
            print(l)
            
        # Also print some of the body to see classes
        if not links:
            print("No links found. Body snippet:")
            print(resp.text[:500])

asyncio.run(test_ddg_html())
