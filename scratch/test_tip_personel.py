import httpx, asyncio
from bs4 import BeautifulSoup

async def test_tip():
    url = "https://tip.adiyaman.edu.tr/tr/personel"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url)
        print("Status:", resp.status_code)
        
        # Look for Hüseyin Kutlu
        if "Hüseyin" in resp.text and "Kutlu" in resp.text:
            print("Hüseyin Kutlu found on the page!")
        else:
            print("Hüseyin Kutlu NOT found on the page text.")

asyncio.run(test_tip())
