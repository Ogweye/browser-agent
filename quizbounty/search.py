from ddgs import DDGS

def search_question(question):
    with DDGS() as ddgs:
        results = list(ddgs.text(question, max_results=3))

    evidence = []

    for r in results:
        snippet = r.get("body", "")[:300]

        evidence.append({
            "title": r.get("title", ""),
            "snippet": snippet
        })

    return evidence