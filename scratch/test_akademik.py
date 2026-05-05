import httpx, asyncio
from bs4 import BeautifulSoup

async def test_akademik():
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        resp = await client.get('https://akademik.adiyaman.edu.tr/')
        print('Status:', resp.status_code)
        
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()
        if "Hüseyin" in text or "HÜSEYİN" in text.upper():
            print("Found Hüseyin!")
        if "Kutlu" in text or "KUTLU" in text.upper():
            print("Found Kutlu!")
            
        print("Total text length:", len(text))

asyncio.run(test_akademik())
