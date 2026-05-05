import httpx, asyncio
from bs4 import BeautifulSoup

async def test_rehber():
    q = "hüseyin kutlu"
    url = f"https://rehber.adiyaman.edu.tr/Search?search={q}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        print("Status:", resp.status_code)
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Look for the name in the results
        if "Hüseyin" in resp.text and "Kutlu" in resp.text:
            print("Hüseyin Kutlu found in Rehber!")
            # Extract email/phone/link
            for tr in soup.find_all("tr"):
                if "Hüseyin" in tr.get_text():
                    print("Row content:", tr.get_text(strip=True))
        else:
            print("Hüseyin Kutlu NOT found in Rehber.")

asyncio.run(test_rehber())
