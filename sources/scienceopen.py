import requests
from datetime import datetime

API_URL = "https://www.scienceopen.com/api/v1/search"

def fetch_scienceopen_papers(max_results: int = 200) -> list[dict]:
    """
    Fetch Long-Covid related papers from ScienceOpen API.
    Returns normalized dicts compatible with the main scraper.
    """

    print("[ScienceOpen] Fetching ScienceOpen papers...")

    params = {
        "q": "long covid OR post-acute sequelae OR PASC OR post covid",
        "page": 1,
        "pageSize": max_results,
        "sort": "date"
    }

    try:
        r = requests.get(API_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ScienceOpen] ERROR fetching data: {e}")
        return []

    results = []

    for item in data.get("records", []):
        try:
            title = item.get("title") or ""
            abstract = item.get("abstract") or ""
            url = item.get("link") or item.get("url") or ""
            doi = item.get("doi") or None

            # Parse date
            pub_date = datetime.today()
            date_raw = item.get("publishedDate") or item.get("date")
            if date_raw:
                try:
                    pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
                except Exception:
                    pass

            # ID
            paper_id = None
            if doi:
                paper_id = f"scienceopen-{doi}"
            else:
                paper_id = f"scienceopen-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "scienceopen",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[ScienceOpen] ERROR parsing item: {e}")
            continue

    print(f"[ScienceOpen] Parsed papers: {len(results)}")
    return results
