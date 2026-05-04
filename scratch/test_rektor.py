
import asyncio
from live_search import get_live_context

async def main():
    question = "rektör kimdir"
    contexts, sources = await asyncio.to_thread(get_live_context, question)
    print(f"Sources: {sources}")
    for i, ctx in enumerate(contexts):
        print(f"--- Context {i} (len {len(ctx)}) ---")
        print(ctx[:500])

if __name__ == "__main__":
    asyncio.run(main())
