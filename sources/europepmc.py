import requests
from utils.date_normalizer import normalize_date

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
            # EuropePMC formats:
            #   - firstPublicationDate: "2024-07-01"
            #   - pubYear: "2024"
            #   - pubDate: "2024-07-01"
            # -----------------------------
            raw_date = (
                item.get("firstPublicationDate")
                or item.get("pubDate")
                or item.get("pubYear")
            )

            pub_date = normalize_date(raw_date)

            # -----------------------------
            # ID construction
            # -----------------------------
            if doi:
                paper_id = f"europepmc-{doi}"
            elif pmid:
                paper_id = f"europepmc-{pmid}"
            else:
                paper_id = f"europepmc-{title[:40].replace(' ', '_')}"

            # -----------------------------
            # Build paper dict
            # -----------------------------
            results.append(
                {
                    "id": paper_id,
                    "title": title.strip(),
                    "abstract": abstract.strip(),
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
