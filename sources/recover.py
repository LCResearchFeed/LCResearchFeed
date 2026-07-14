import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://recovercovid.org"
RECOVER_URL = f"{BASE_URL}/publications"

# ---------------------------------------------------------
# Robust date parser for RECOVER
# ---------------------------------------------------------
def parse_recover_date(raw: str) -> datetime | None:
    if not raw:
        return None

    raw = raw.strip()

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%B %d, %Y",     # October 3, 2024
        "%b %d, %Y",     # Oct 3, 2024
        "%Y",            # fallback year
    ]

    for fmt in formats:
        try:
            return datetime.strptime(raw[:len(fmt)], fmt)
        except Exception:
            continue

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
            # -----------------------------
            # Title + URL
            # -----------------------------
            title_el = item.select_one("h3 a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")
            if url and not url.startswith("http"):
                url = BASE_URL + url

            # -----------------------------
            # Fetch detail page
            # -----------------------------
            abstract = ""
            pub_date = None

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
                    pub_date = parse_recover_date(raw_date)

            except Exception as e:
                print(f"[RECOVER] WARNING: Could not fetch detail page: {e}")

            # Skip papers without valid date
            if pub_date is None:
                print(f"[RECOVER] Skipping paper without valid date: {title[:50]}")
                continue

            # -----------------------------
            # Build ID
            # -----------------------------
            paper_id = (
                "recover-" +
                title[:40].replace(" ", "-").replace("/", "-").lower()
            )

            # -----------------------------
            # Build paper dict
            # -----------------------------
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
