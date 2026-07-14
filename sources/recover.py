import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://recovercovid.org"
RECOVER_URL = f"{BASE_URL}/publications"


# ---------------------------------------------------------
# Universal date parser (used by ALL sources)
# ---------------------------------------------------------
def parse_any_date(raw: str | None) -> datetime | None:
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

    # e.g. "October 3, 2024"
    if len(parts) == 3 and "," in parts[1]:
        try:
            return datetime.strptime(raw, "%B %d, %Y")
        except Exception:
            pass

    # e.g. "Oct 3, 2024"
    if len(parts) == 3 and "," in parts[1]:
        try:
            return datetime.strptime(raw, "%b %d, %Y")
        except Exception:
            pass

    # e.g. "14 July 2024"
    if len(parts) == 3 and parts[1] in text_months:
        try:
            day = int(parts[0])
            month = text_months[parts[1]]
            year = int(parts[2])
            return datetime(year, month, day)
        except Exception:
            pass

    # e.g. "2024 October"
    if len(parts) == 2 and parts[1] in text_months:
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
def fetch_recover_papers(max_results: int = 200) -> list[dict]:
    print("[RECOVER] Fetching RECOVER publications...")

    try:
        r = requests.get(
            RECOVER_URL,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[RECOVER] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.views-row")

    if not items:
        print("[RECOVER] No publications found.")
        return []

    results = []

    for item in items[:max_results]:
        try:
            # Title + URL
            title_el = item.select_one("h3 a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")
            if url and not url.startswith("http"):
                url = BASE_URL + url

            abstract = ""
            pub_date = None

            # Fetch detail page
            try:
                detail = requests.get(
                    url,
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                detail.raise_for_status()
                dsoup = BeautifulSoup(detail.text, "html.parser")

                # Abstract
                body = dsoup.select_one("div.field--name-body")
                if body:
                    abstract = body.get_text(strip=True)

                # Date
                date_tag = dsoup.select_one("time")
                if date_tag:
                    raw_date = date_tag.get("datetime") or date_tag.get_text(strip=True)
                    pub_date = parse_any_date(raw_date)

            except Exception as e:
                print(f"[RECOVER] WARNING: Could not fetch detail page: {e}")

            # Skip papers without valid date
            if pub_date is None:
                print(f"[RECOVER] Skipping paper without valid date: {title[:50]}")
                continue

            # ID
            paper_id = (
                "recover-" +
                title[:40].replace(" ", "-").replace("/", "-").lower()
            )

            results.append({
                "id": paper_id,
                "title": title,
                "abstract": abstract,
                "url": url,
                "source": "recover",
                "mesh": [],
                "date": pub_date,
            })

        except Exception as e:
            print(f"[RECOVER] ERROR parsing item: {e}")
            continue

    print(f"[RECOVER] Parsed papers: {len(results)}")
    return results
