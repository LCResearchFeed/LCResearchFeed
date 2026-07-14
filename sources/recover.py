import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from typing import Optional, List, Dict


BASE_URL = "https://recovercovid.org"
RECOVER_URL = f"{BASE_URL}/publications"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123 Safari/537.36"
}


# ---------------------------------------------------------
# Universele datumparser
# ---------------------------------------------------------
def parse_any_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None

    raw = raw.strip()

    # ISO
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
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12,
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9,
        "Oct": 10, "Nov": 11, "Dec": 12,
    }

    parts = raw.split()

    # "14 July 2024"
    if len(parts) == 3 and parts[1] in months:
        try:
            return datetime(int(parts[2]), months[parts[1]], int(parts[0]))
        except Exception:
            pass

    # "July 2024"
    if len(parts) == 2 and parts[0] in months and parts[1].isdigit():
        try:
            return datetime(int(parts[1]), months[parts[0]], 1)
        except Exception:
            pass

    # "2024 July"
    if len(parts) == 2 and parts[1] in months:
        try:
            return datetime(int(parts[0]), months[parts[1]], 1)
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

    # Ranges: "2024 Fall-Winter"
    if "-" in raw:
        left = raw.split("-")[0].strip()
        parts_left = left.split()
        if len(parts_left) == 2 and parts_left[1] in seasons:
            try:
                return datetime(int(parts_left[0]), seasons[parts_left[1]], 1)
            except Exception:
                pass

    # ANY year → 01-01-YYYY
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    if m:
        return datetime(int(m.group()), 1, 1)

    return None


# ---------------------------------------------------------
# PubMed fallback (alleen datum)
# ---------------------------------------------------------
def fetch_pubmed_date(title: str) -> Optional[datetime]:
    try:
        r = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": title, "retmax": 1},
            timeout=10,
        )
        r.raise_for_status()
        pmids = re.findall(r"<Id>(\d+)</Id>", r.text)
        if not pmids:
            return None

        pmid = pmids[0]

        r2 = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "xml"},
            timeout=10,
        )
        r2.raise_for_status()

        # Zoek PubDate / MedlineDate
        m = re.search(r"<PubDate>.*?<Year>(\d+)</Year>.*?<Month>(.*?)</Month>", r2.text, re.S)
        if m:
            year = int(m.group(1))
            month = m.group(2)
            return parse_any_date(f"{year} {month}")

        m2 = re.search(r"<MedlineDate>(.*?)</MedlineDate>", r2.text)
        if m2:
            return parse_any_date(m2.group(1))

    except Exception:
        return None

    return None


# ---------------------------------------------------------
# Main RECOVER fetcher
# ---------------------------------------------------------
def fetch_recover_papers(max_results: int = 200) -> List[Dict]:
    print("[RECOVER] Fetching RECOVER publications...")

    try:
        r = requests.get(RECOVER_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("[RECOVER] ERROR fetching page:", e)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.views-row")

    if not items:
        print("[RECOVER] No publications found.")
        return []

    results = []

    for item in items[:max_results]:
        try:
            title_el = item.select_one("h3 a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")
            if url and not url.startswith("http"):
                url = BASE_URL + url

            # Fetch detail page
            try:
                detail = requests.get(url, headers=HEADERS, timeout=20)
                detail.raise_for_status()
                dsoup = BeautifulSoup(detail.text, "html.parser")
            except Exception as e:
                print("[RECOVER] WARNING: Could not fetch detail page:", e)
                continue

            # 1. Try <time>
            date_tag = dsoup.select_one("time")
            pub_date = None

            if date_tag:
                raw_date = date_tag.get("datetime") or date_tag.get_text(strip=True)
                pub_date = parse_any_date(raw_date)

            # 2. Fallback: zoek maand + jaar in tekst
            if pub_date is None:
                text = dsoup.get_text(" ", strip=True)
                m = re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}",
                    text,
                    re.I,
                )
                if m:
                    pub_date = parse_any_date(m.group())

            # 3. PubMed fallback
            if pub_date is None:
                pub_date = fetch_pubmed_date(title)

            # 4. Als nog steeds geen datum → skip
            if pub_date is None:
                print("[RECOVER] Skipping paper without valid date:", title[:50])
                continue

            # Abstract
            abstract = ""
            body = dsoup.select_one("div.field--name-body")
            if body:
                abstract = body.get_text(strip=True)

            paper_id = "recover-" + re.sub(r"[^a-z0-9]+", "-", title.lower())[:40]

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
            print("[RECOVER] ERROR parsing item:", e)
            continue

    print("[RECOVER] Parsed papers:", len(results))
    return results
