import requests
from datetime import datetime
from typing import Optional, List, Dict

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


# ---------------------------------------------------------
# Robust EuropePMC date parser (NO fallback to today)
# ---------------------------------------------------------
def parse_europepmc_date(raw: Optional[str]) -> Optional[datetime]:
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

    # Text months (e.g. "2024 Oct")
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
    if len(parts) == 2 and parts[1] in text_months:
        try:
            year = int(parts[0])
            month = text_months[parts[1]]
            return datetime(year, month, 1)
        except Exception:
            pass

    # Seasons (EuropePMC sometimes uses these)
    seasons = {
        "Winter": 1,   # Jan
        "Spring": 3,   # Mar
        "Summer": 6,   # Jun
        "Autumn": 9,   # Sep
        "Fall": 9,     # Sep
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
def fetch_europepmc_papers(max_results: int = 200) -> List[Dict]:
    print("[EuropePMC] Fetching EuropePMC papers...")

    query = 'LONG COVID OR "post-acute sequelae" OR PASC'
    params = {
        "query": query,
        "format": "json",
        "pageSize": max_results,
    }

    try:
        r = requests.get(API_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[EuropePMC] ERROR fetching data: {e}")
        return []

    results = []
    items = data.get("resultList", {}).get("result", [])

    for item in items:
        try:
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstractText") or "").strip()

            doi = item.get("doi")
            pmid = item.get("pmid")

            # -----------------------------
            # URL extraction
            # -----------------------------
            # URL extraction (skip papers without any valid link)
            link = None
            full_urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])

            if full_urls:
                link = full_urls[0].get("url", "")
            elif pmid:
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif doi:
                link = f"https://doi.org/{doi}"

            # Skip papers without any usable link
            if not link:
                print(f"[EuropePMC] Skipping paper without valid link: {title[:50]}")
                continue


            # -----------------------------
            # DATE extraction (no fallback)
            # -----------------------------
            raw_date = (
                item.get("firstPublicationDate")
                or item.get("pubDate")
                or item.get("pubYear")
            )

            pub_date = parse_europepmc_date(raw_date)

            # Skip papers without valid date
            if pub_date is None:
                print(f"[EuropePMC] Skipping paper without valid date: {title[:50]}")
                continue

            # -----------------------------
            # ID construction
            # -----------------------------
            if doi:
                paper_id = f"europepmc-{doi}"
            elif pmid:
                paper_id = f"europepmc-{pmid}"
            else:
                safe_title = title[:40].replace(" ", "_")
                paper_id = f"europepmc-{safe_title}"

            # -----------------------------
            # Build paper dict
            # -----------------------------
            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": link,
                    "source": "europepmc",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[EuropePMC] ERROR parsing item: {e}")
            continue

    print(f"[EuropePMC] Parsed papers: {len(results)}")
    return results
