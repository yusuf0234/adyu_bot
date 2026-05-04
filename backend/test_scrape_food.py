import asyncio
from live_search import get_live_context, scrape_url

def main():
    print("Testing scrape_url directly on sksdb.adiyaman.edu.tr/tr/yemekhane/yemek-menusu")
    url, text = scrape_url("https://sksdb.adiyaman.edu.tr/tr/yemekhane/yemek-menusu")
    print("Scraped length:", len(text))
    print("Snippet:", text[:500])
    
    print("\nTesting get_live_context for 'bugün yemekte ne var'")
    contexts, sources = get_live_context("bugün yemekte ne var")
    print("Contexts:", len(contexts))
    for c in contexts:
        print("Context snippet:", c[:200])

if __name__ == '__main__':
    main()
