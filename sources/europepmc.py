import requests
from datetime import datetime
from typing import Optional, List, Dict

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


# ---------------------------------------------------------
# Robust EuropePMC date parser (NO fallback to today)
# ---------------------------------------------------------
def parse_europepmc_date(raw: Optional[str]) -> Optional[datetime]:
    """
    Parse EuropePMC date formats.
    Returns None if the date cannot be parsed.
    Supported formats:
        - YYYY
        - YYYY-MM
        - YYYY-MM-DD
        - ISO timestamps with Z or timezone
    """

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
    if len(raw) == 7:
        try:
            return datetime.strptime(raw, "%Y-%m")
        except Exception:
            pass

    # YYYY
    if len(raw) == 4:
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
            link = ""
            full_urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
            if full_urls:
                link = full_urls[0].get("url", "")
            elif pmid:
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif doi:
                link = f"https://doi.org/{doi}"

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
