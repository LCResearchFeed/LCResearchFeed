import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_NATURE = "https://www.nature.com"


def _parse_nature_date(raw: str) -> datetime:
    """
    Robust parser for Nature date formats.
    Supports:
        - "2024-07-01"
        - "2024-07-01T00:00:00Z"
        - "2024-07-01T00:00:00"
        - "2024-07-01T00:00:00+01:00"
        - fallback: today
    """

    if not raw:
        return datetime.today()

    raw = raw.strip()

    # ISO formats with time
    iso_formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in iso_formats:
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            pass

    # YYYY-MM-DD (truncate time)
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        pass

    return datetime.today()


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
        r.raise_for_status()
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
        # -----------------------------
        # Title
        # -----------------------------
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
        # Snippet / abstract preview
        # -----------------------------
        snippet_tag = (
            a.select_one("p")
            or a.select_one("[data-testid='search-snippet']")
        )
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        # -----------------------------
        # Date
        # -----------------------------
        pub_date = datetime.today()
        date_tag = a.select_one("time")

        if date_tag:
            raw_date = date_tag.get("datetime") or date_tag.get_text(strip=True)
            pub_date = _parse_nature_date(raw_date)

        # -----------------------------
        # Build paper dict
        # -----------------------------
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
