import httpx, asyncio
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

async def test_uni_search():
    q = "hüseyin kutlu"
    url = f"https://www.adiyaman.edu.tr/tr/arama?q={quote_plus(q)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        results_found = False
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text().strip()
            if "hüseyin" in text.lower() or "kutlu" in text.lower():
                print(f"Found Match: {text} -> {href}")
                results_found = True
        
        if not results_found:
            print("No results found on the search page for the query.")

asyncio.run(test_uni_search())
