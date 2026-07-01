import requests
from datetime import datetime

API_URL = "https://www.ncbi.nlm.nih.gov/research/litcovid/api/records/"

def fetch_litcovid_papers(max_results: int = 200) -> list[dict]:
    print("[LitCovid] Fetching LitCovid papers...")

    params = {
        "query": "long covid OR post-acute sequelae OR PASC OR post covid",
        "page": 1,
        "pageSize": max_results,
    }

    try:
        r = requests.get(API_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[LitCovid] ERROR fetching data: {e}")
        return []

    results = []
    for item in data.get("records", []):
        try:
            pmid = item.get("pmid") or item.get("uid")
            title = item.get("title") or ""
            abstract = item.get("abstract") or ""
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            date_raw = item.get("publish_time") or ""
            pub_date = datetime.today()
            if date_raw:
                try:
                    pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
                except Exception:
                    pass

            results.append(
                {
                    "id": f"litcovid-{pmid}" if pmid else f"litcovid-{title[:40]}",
                    "title": title,
                    "abstract": abstract,
                    "url": link,
                    "source": "litcovid",
                    "mesh": [],
                    "date": pub_date,
                }
            )
        except Exception as e:
            print(f"[LitCovid] ERROR parsing item: {e}")
            continue

    print(f"[LitCovid] Parsed papers: {len(results)}")
    return results
