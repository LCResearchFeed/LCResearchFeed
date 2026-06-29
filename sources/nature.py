import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_NATURE = "https://www.nature.com"

# ---------------------------------------------------------
# Nature: HTML scraping
# ---------------------------------------------------------

def fetch_nature_papers(max_results: int = 50) -> list[dict]:
    """
    Scrape Nature search results for Long COVID.
    Returns standardized paper dictionaries.
    """

    url = f"{BASE_NATURE}/search?q=long+covid&order=date"

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )
    except Exception:
        return []

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Nature uses multiple possible structures
    articles = (
        soup.select("article")
        or soup.select("[data-testid='search-result']")
        or soup.select("div.search-results__item")
    )

    results = []

    for a in articles[:max_results]:
        # Title
        title_tag = (
            a.select_one("h3 a")
            or a.select_one("h2 a")
            or a.select_one("a[href]")
        )
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if not href:
            continue

        link = href if href.startswith("http") else BASE_NATURE + href

        # Snippet / abstract preview
        snippet_tag = (
            a.select_one("p")
            or a.select_one("[data-testid='search-snippet']")
        )
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        # Date
        pub_date = datetime.today()
        date_tag = a.select_one("time")

        if date_tag:
            dt = date_tag.get("datetime") or date_tag.get_text(strip=True)
            if dt:
                # Try multiple formats
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        pub_date = datetime.strptime(dt[:len(fmt)], fmt)
                        break
                    except Exception:
                        continue

        results.append({
            "id": link,
            "title": title,
            "abstract": snippet,
            "url": link,
            "source": "nature",
            "mesh": [],
            "date": pub_date,
        })

    # Deduplicate by URL
    final = list({item["id"]: item for item in results}.values())
    return final
