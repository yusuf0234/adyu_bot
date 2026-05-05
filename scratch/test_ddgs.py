from duckduckgo_search import DDGS

def test_ddg():
    print("Testing HTML backend...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text("hüseyin kutlu kimdir site:adiyaman.edu.tr", backend="html", max_results=3))
            print(results)
    except Exception as e:
        print("HTML Error:", e)

    print("\nTesting Lite backend...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text("hüseyin kutlu kimdir site:adiyaman.edu.tr", backend="lite", max_results=3))
            print(results)
    except Exception as e:
        print("Lite Error:", e)

if __name__ == "__main__":
    test_ddg()
