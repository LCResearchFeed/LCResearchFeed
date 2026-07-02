import requests
from datetime import datetime

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _parse_europepmc_date(raw: str) -> datetime:
    """
    Robust parser for EuropePMC date formats.
    Supports:
        - "2024"
        - "2024-07"
        - "2024-07-01"
        - "2024-07-01T00:00:00Z"
        - "2024-07-01T00:00:00"
        - "2024-07-01T00:00:00+01:00"
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

    # Fallback
    return datetime.today()


def fetch_europepmc_papers(max_results: int = 200) -> list[dict]:
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

    for item in data.get("resultList", {}).get("result", []):
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
            # DATE extraction (robust)
            # -----------------------------
            raw_date = (
                item.get("firstPublicationDate")
                or item.get("pubDate")
                or item.get("pubYear")
            )

            pub_date = _parse_europepmc_date(raw_date)

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
