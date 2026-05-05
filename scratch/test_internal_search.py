import httpx, asyncio

async def test_akademik_search():
    async with httpx.AsyncClient() as client:
        # Many universities use simple GET search: /Arama?q=isim or POST
        resp = await client.get('https://akademik.adiyaman.edu.tr/arama?q=hüseyin+kutlu', follow_redirects=True)
        print("GET /arama?q=", resp.status_code)
        if "Hüseyin" in resp.text: print("Found via GET /arama")

        resp = await client.get('https://akademik.adiyaman.edu.tr/Search?q=hüseyin+kutlu', follow_redirects=True)
        print("GET /Search?q=", resp.status_code)
        if "Hüseyin" in resp.text: print("Found via GET /Search")
        
asyncio.run(test_akademik_search())
