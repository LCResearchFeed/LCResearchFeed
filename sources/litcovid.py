import requests
from datetime import datetime

def fetch_litcovid_papers(max_results: int = 200) -> list[dict]:
    """
    Fetch Long-Covid related papers from LitCovid API.
    Returns normalized dicts compatible with the main scraper.
    """

    url = "https://www.ncbi.nlm.nih.gov/research/litcovid/api/records"
    params = {
        "query": "long covid OR post-acute sequelae OR PASC OR post covid",
        "limit": max_results
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[LitCovid] ERROR fetching data: {e}")
        return []

    results = []

    for item in data.get("records", []):
        try:
            pmid = item.get("pmid") or item.get("uid") or None
            title = item.get("title") or ""
            abstract = item.get("abstract") or ""
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else item.get("url", "")

            # Parse date
            date_raw = item.get("publish_time") or ""
            pub_date = datetime.today()
            if date_raw:
                try:
                    pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
                except Exception:
                    pass

            results.append(
                {
                    "id": f"litcovid-{pmid}" if pmid else f"litcovid-{title[:30]}",
                    "title": title,
                    "abstract": abstract,
                    "url": link,
                    "source": "litcovid",
                    "mesh": [],  # LitCovid does not provide MESH
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[LitCovid] ERROR parsing item: {e}")
            continue

    print(f"[LitCovid] Parsed papers: {len(results)}")
    return results
