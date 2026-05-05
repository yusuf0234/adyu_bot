import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from live_search import get_live_context

async def main():
    question = "şakir gündoğar kimdir"
    contexts, sources = await get_live_context(question)
    print(f"Sources: {sources}")
    for i, ctx in enumerate(contexts):
        print(f"--- Context {i} ({len(ctx)} chars) ---")
        print(ctx[:500])

if __name__ == "__main__":
    asyncio.run(main())
