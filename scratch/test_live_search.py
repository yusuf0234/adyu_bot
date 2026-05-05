import asyncio
import sys
sys.path.append('backend')
from live_search import get_live_context

async def test():
    ctx, urls = await get_live_context("hüseyin kutlu kimdir")
    print("Found Context:", len(ctx))
    print("Found URLs:", urls)

if __name__ == "__main__":
    asyncio.run(test())
