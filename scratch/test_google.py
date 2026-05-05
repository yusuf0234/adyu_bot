import httpx, asyncio, re

async def test_google():
    q = 'hüseyin kutlu kimdir site:adiyaman.edu.tr'
    google_url = f'https://www.google.com/search?q={q}&num=5&hl=tr'
    async with httpx.AsyncClient(timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}) as client:
        resp = await client.get(google_url)
        print('Status:', resp.status_code)
        print('Length:', len(resp.text))
        print('Head:', resp.text[:500])

asyncio.run(test_google())
