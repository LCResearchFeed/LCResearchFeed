import requests
from datetime import datetime
from bs4 import BeautifulSoup

BASE_URL = "https://www.ncbi.nlm.nih.gov/research/coronavirus/"

def fetch_litcovid_html_long_covid(max_results: int = 200) -> list[dict]:
    print("[LitCovid] Fetching HTML Long Covid papers...")

    params = {
        "text": "long covid",
        "page": 1,
    }

    try:
        r = requests.get(
            BASE_URL,
            params=params,
            timeout=20,
            headers={"Accept": "text/html"}
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[LitCovid] ERROR fetching HTML: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Elke paper staat in <article class="result" data-uid="PMID">
    for art in soup.select("article.result[data-uid]"):
        try:
            pmid = art.get("data-uid")

            title_el = art.select_one("a.docsum-title")
            title = title_el.get_text(strip=True) if title_el else ""

            abstract_el = art.select_one("div.docsum-content")
            abstract = abstract_el.get_text(strip=True) if abstract_el else ""

            date_el = art.select_one(".docsum-pubdate")
            date_raw = date_el.get_text(strip=True) if date_el else ""
            pub_date = datetime.today()

            try:
                pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
            except Exception:
                pass

            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            results.append(
                {
                    "id": f"litcovid-{pmid}",
                    "title": title,
                    "abstract": abstract,
                    "url": link,
                    "source": "litcovid-html",
                    "mesh": [],
                    "date": pub_date,
                }
            )

            if len(results) >= max_results:
                break

        except Exception as e:
            print(f"[LitCovid] ERROR parsing HTML item: {e}")
            continue

    print(f"[LitCovid] Parsed HTML papers: {len(results)}")
    return results
