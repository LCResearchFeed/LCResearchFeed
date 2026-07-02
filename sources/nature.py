import requests
from bs4 import BeautifulSoup
from utils.date_normalizer import normalize_date

BASE_NATURE = "https://www.nature.com"


def fetch_nature_papers(max_results: int = 50) -> list[dict]:
    """
    Scrape Nature search results for Long COVID.
    Returns standardized paper dictionaries with normalized dates.
    """

    url = f"{BASE_NATURE}/search?q=long+covid&order=date"

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )
        r.raise_for_status()
    except Exception:
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

        # -----------------------------
        # TITLE + URL
        #-----------------------------
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

        # -----------------------------
        # SNIPPET / ABSTRACT PREVIEW
        #-----------------------------
        snippet_tag = (
            a.select_one("p")
            or a.select_one("[data-testid='search-snippet']")
        )
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        # -----------------------------
        # DATE (robust)
        # Nature formats:
        #   <time datetime="2024-07-01">
        #   <time>2024-07-01</time>
        #   <time datetime="2024-07-01T12:00:00Z">
        # -----------------------------
        raw_date = None
        date_tag = a.select_one("time")

        if date_tag:
            raw_date = date_tag.get("datetime") or date_tag.get_text(strip=True)

        pub_date = normalize_date(raw_date)

        # -----------------------------
        # BUILD PAPER DICT
        #-----------------------------
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
