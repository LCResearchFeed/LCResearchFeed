import requests
from bs4 import BeautifulSoup
from datetime import datetime

RKI_URL = "https://www.rki.de/EN/Content/infections/epidemiology/long_covid/long_covid_node.html"

def fetch_rki_papers(max_results: int = 200) -> list[dict]:
    """
    Scrape RKI Long-Covid publications.
    Returns normalized dicts compatible with the main scraper.
    """

    print("[RKI] Fetching RKI Long-Covid publications...")

    try:
        r = requests.get(RKI_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[RKI] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # RKI uses <li> blocks inside publication lists
    items = soup.select("li a[href]")
    if not items:
        print("[RKI] No publication items found.")
        return []

    for item in items[:max_results]:
        try:
            title = item.get_text(strip=True)
            url = item.get("href")

            if url and not url.startswith("http"):
                url = "https://www.rki.de" + url

            # Fetch detail page for abstract/snippet
            abstract = ""
            pub_date = datetime.today()

            try:
                detail = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                detail.raise_for_status()
                dsoup = BeautifulSoup(detail.text, "html.parser")

                # Abstract/snippet
                ptag = dsoup.find("p")
                if ptag:
                    abstract = ptag.get_text(strip=True)

                # Date
                time_tag = dsoup.find("time")
                if time_tag:
                    dt = time_tag.get("datetime") or time_tag.get_text(strip=True)
                    if dt:
                        try:
                            pub_date = datetime.strptime(dt[:10], "%Y-%m-%d")
                        except Exception:
                            pass

            except Exception as e:
                print(f"[RKI] WARNING: Could not fetch detail page: {e}")

            paper_id = f"rki-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "rki",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[RKI] ERROR parsing item: {e}")
            continue

    print(f"[RKI] Parsed papers: {len(results)}")
    return results
