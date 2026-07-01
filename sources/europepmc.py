import requests
from datetime import datetime

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

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
            title = item.get("title") or ""
            abstract = item.get("abstractText") or ""
            doi = item.get("doi")
            pmid = item.get("pmid")
            url = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
            link = ""
            if url:
                link = url[0].get("url", "")
            elif pmid:
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            date_raw = item.get("firstPublicationDate") or item.get("pubYear")
            pub_date = datetime.today()
            if date_raw:
                try:
                    pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
                except Exception:
                    pass

            paper_id = f"europepmc-{doi}" if doi else f"europepmc-{pmid or title[:40]}"

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
