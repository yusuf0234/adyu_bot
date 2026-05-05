from duckduckgo_search import DDGS
with DDGS() as ddgs:
    results = list(ddgs.text("python programming", max_results=3))
    print(results)
