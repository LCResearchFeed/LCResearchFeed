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

    # ----------------------------------------
    # 0. Extract ANY year first (for weird RECOVER formats)
    # ----------------------------------------
    import re
    year_match = re.search(r"\b(19|20)\d{2}\b", raw)
    if year_match:
        year = int(year_match.group())

        # If the string contains "online", "updated", "ahead", "preprint", etc.
        if any(x in raw.lower() for x in [
            "online", "updated", "ahead", "preprint", "release", "version"
        ]):
            return datetime(year, 1, 1)

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

    # "October 3, 2024"
    if len(parts) == 3 and "," in parts[1]:
        try:
            return datetime.strptime(raw, "%B %d, %Y")
        except Exception:
            pass

    # "Oct 3, 2024"
    if len(parts) == 3 and "," in parts[1]:
        try:
            return datetime.strptime(raw, "%b %d, %Y")
        except Exception:
            pass

    # "14 July 2024"
    if len(parts) == 3 and parts[1] in text_months:
        try:
            return datetime(int(parts[2]), text_months[parts[1]], int(parts[0]))
        except Exception:
            pass

    # "2024 October"
    if len(parts) == 2 and parts[1] in text_months:
        try:
            return datetime(int(parts[0]), text_months[parts[1]], 1)
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
            return datetime(int(parts[0]), seasons[parts[1]], 1)
        except Exception:
            pass

    # ----------------------------------------
    # Final fallback: ANY year → 01-01-YYYY
    # ----------------------------------------
    if year_match:
        return datetime(year, 1, 1)

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
