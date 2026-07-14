import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict

BASE_NATURE = "https://www.nature.com"


# ---------------------------------------------------------
# Universal date parser (used by ALL sources)
# ---------------------------------------------------------
def parse_any_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None

    raw = raw.strip()

    # ISO formats
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

    # YYYY-MM
    try:
        return datetime.strptime(raw, "%Y-%m")
    except Exception:
        pass

    # Text months
    text_months = {
        "Jan": 1, "January": 1,
        "Feb": 2, "February": 2,
        "Mar": 3, "March": 3,
        "Apr": 4, "April": 4,
        "May": 5,
        "Jun": 6, "June": 6,
        "Jul": 7, "July": 7,
        "Aug": 8, "August": 8,
        "Sep": 9, "Sept": 9, "September": 9,
        "Oct": 10, "October": 10,
        "Nov": 11, "November": 11,
        "Dec": 12, "December": 12,
    }

    parts = raw.split()
    if len(parts) == 3 and parts[1] in text_months:
        # e.g. "14 July 2024"
        try:
            day = int(parts[0])
            month = text_months[parts[1]]
            year = int(parts[2])
            return datetime(year, month, day)
        except Exception:
            pass

    if len(parts) == 2 and parts[1] in text_months:
        # e.g. "2024 July"
        try:
            year = int(parts[0])
            month = text_months[parts[1]]
            return datetime(year, month, 1)
        except Exception:
            pass

    # Seasons
    seasons = {
        "Winter": 1,
        "Spring": 3,
        "Summer": 6,
        "Autumn": 9,
        "Fall": 9,
    }

    if len(parts) == 2 and parts[1] in seasons:
        try:
            year = int(parts[0])
            month = seasons[parts[1]]
            return datetime(year, month, 1)
        except Exception:
            pass

    # YYYY only
    if len(raw) == 4 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y")
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
            pub_date = parse_any_date(raw_date)
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
