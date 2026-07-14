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

    # ----------------------------------------
    # 1. ISO formats
    # ----------------------------------------
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

    # ----------------------------------------
    # 2. YYYY-MM-DD
    # ----------------------------------------
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        pass

    # ----------------------------------------
    # 3. YYYY-MM
    # ----------------------------------------
    try:
        return datetime.strptime(raw, "%Y-%m")
    except Exception:
        pass

    # ----------------------------------------
    # 4. Text months
    # ----------------------------------------
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

    # ----------------------------------------
    # 5. "Published: July 2024"
    # ----------------------------------------
    if raw.lower().startswith("published:"):
        raw2 = raw.split(":", 1)[1].strip()
        parts2 = raw2.split()

        # Month + Year
        if len(parts2) == 2 and parts2[0] in text_months:
            try:
                return datetime(int(parts2[1]), text_months[parts2[0]], 1)
            except Exception:
                pass

        # Year only
        if len(parts2) == 1 and parts2[0].isdigit():
            return datetime(int(parts2[0]), 1, 1)

    # ----------------------------------------
    # 6. "14 July 2024"
    # ----------------------------------------
    if len(parts) == 3 and parts[1] in text_months:
        try:
            return datetime(int(parts[2]), text_months[parts[1]], int(parts[0]))
        except Exception:
            pass

    # ----------------------------------------
    # 7. "July 2024"
    # ----------------------------------------
    if len(parts) == 2 and parts[0] in text_months and parts[1].isdigit():
        try:
            return datetime(int(parts[1]), text_months[parts[0]], 1)
        except Exception:
            pass

    # ----------------------------------------
    # 8. "2024 July"
    # ----------------------------------------
    if len(parts) == 2 and parts[1] in text_months:
        try:
            return datetime(int(parts[0]), text_months[parts[1]], 1)
        except Exception:
            pass

    # ----------------------------------------
    # 9. Seasons
    # ----------------------------------------
    seasons = {
        "Winter": 1,
        "Spring": 3,
        "Summer": 6,
        "Autumn": 9,
        "Fall": 9,
    }

    if len(parts) == 2 and parts[1] in seasons:
        try:
            return datetime(int(parts[0]), seasons[parts[1]], 1)
        except Exception:
            pass

    # ----------------------------------------
    # 10. Ranges: "2024 Fall-Winter"
    # ----------------------------------------
    if "-" in raw:
        left = raw.split("-")[0].strip()
        parts_left = left.split()
        if len(parts_left) == 2 and parts_left[1] in seasons:
            try:
                return datetime(int(parts_left[0]), seasons[parts_left[1]], 1)
            except Exception:
                pass

    # ----------------------------------------
    # 11. Extract ANY year → ALWAYS 01-01-YYYY
    # ----------------------------------------
    import re
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    if m:
        year = int(m.group())
        return datetime(year, 1, 1)

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
