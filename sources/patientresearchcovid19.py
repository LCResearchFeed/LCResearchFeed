import requests
from bs4 import BeautifulSoup
from datetime import datetime

PRC_BASE_URL = "https://patientresearchcovid19.com"
PRC_PUBLICATIONS_URL = f"{PRC_BASE_URL}/publications/"

def fetch_patientresearchcovid19_papers(max_results: int = 200) -> list[dict]:
    """
    Scrape Patient Led Research Collaborative (patientresearchcovid19.com) publications.
    Returns normalized dicts compatible met de main scraper.
    """

    print("[PatientResearch] Fetching Patient Led Research Collaborative publications...")

    try:
        r = requests.get(PRC_PUBLICATIONS_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[PatientResearch] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results: list[dict] = []

    # De publications-pagina gebruikt article-blokken voor individuele publicaties
    articles = soup.find_all("article")
    if not articles:
        # fallback: probeer generieke selectors
        articles = soup.select("div.post, div.entry, li a[href]")
        if not articles:
            print("[PatientResearch] No publication items found.")
            return []

    for a in articles[:max_results]:
        try:
            # Titel
            title_tag = a.find("h3") or a.find("h2") or a.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # URL (link naar paper of detailpagina)
            link_tag = a.find("a", href=True)
            url = ""
            if link_tag:
                url = link_tag["href"]
                if url and not url.startswith("http"):
                    url = PRC_BASE_URL + url

            # Abstract/snippet (kort stukje tekst)
            abstract = ""
            # eerst een <p> binnen het article
            p_tag = a.find("p")
            if p_tag:
                abstract = p_tag.get_text(strip=True)
            # fallback: als we alleen een <li> hebben
            if not abstract and isinstance(a, BeautifulSoup):
                abstract = a.get_text(strip=True)

            # Datum
            pub_date = datetime.today()
            time_tag = a.find("time")
            if time_tag:
                dt_raw = time_tag.get("datetime") or time_tag.get_text(strip=True)
                if dt_raw:
                    try:
                        pub_date = datetime.strptime(dt_raw[:10], "%Y-%m-%d")
                    except Exception:
                        pass

            # ID
            paper_id = f"patientresearch-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "patientresearchcovid19",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[PatientResearch] ERROR parsing article: {e}")
            continue

    print(f"[PatientResearch] Parsed papers: {len(results)}")
    return results
