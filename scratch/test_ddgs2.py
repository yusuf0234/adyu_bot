from duckduckgo_search import DDGS

def test_ddg():
    with DDGS() as ddgs:
        results = list(ddgs.text("hüseyin kutlu adıyaman üniversitesi", max_results=3))
        print("API Results:", [r.get('href') for r in results])

        results = list(ddgs.text("hüseyin kutlu adıyaman üniversitesi", backend="html", max_results=3))
        print("HTML Results:", [r.get('href') for r in results])

        results = list(ddgs.text("hüseyin kutlu adıyaman üniversitesi", backend="lite", max_results=3))
        print("Lite Results:", [r.get('href') for r in results])

if __name__ == "__main__":
    test_ddg()
