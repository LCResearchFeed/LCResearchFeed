import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict

BASE_NATURE = "https://www.nature.com"


# ---------------------------------------------------------
# Robust Nature date parser (NO fallback)
# ---------------------------------------------------------
def parse_nature_date(raw: Optional[str]) -> Optional[datetime]:
    """
    Parse Nature date formats.
    Returns None if the date cannot be parsed.
    Supported:
        - YYYY-MM-DD
        - YYYY-MM-DDT00:00:00Z
        - YYYY-MM-DDT00:00:00
        - YYYY-MM-DDT00:00:00+01:00
    """

    if not raw:
        return None

    raw = raw.strip()

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

    # YYYY-MM-DD
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        pass

    return None


# ---------------------------------------------------------
# Main fetcher
# ---------------------------------------------------------
def fetch_nature_papers(max_results: int = 50) -> List[Dict]:
    print("[Nature] Fetching Nature papers...")

    url = f"{BASE_NATURE}/search?q=long+covid&order=date"

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[Nature] ERROR fetching data: {e}")
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
        date_tag = a.select_one("time")
        if date_tag:
            raw_date = date_tag.get("datetime") or date_tag.get_text(strip=True)
            pub_date = parse_nature_date(raw_date)
        else:
            pub_date = None

        # Skip papers without valid date
        if pub_date is None:
            print(f"[Nature] Skipping paper without valid date: {title[:50]}")
            continue

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
    print(f"[Nature] Parsed papers: {len(final)}")
    return final
