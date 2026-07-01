import requests
from bs4 import BeautifulSoup
from datetime import datetime

LCWEB_URL = "https://longcovidweb.com/published-studies"

def fetch_longcovidweb_papers(max_results: int = 200) -> list[dict]:
    """
    Scrape LongCovidWeb curated LC publications.
    Returns normalized dicts compatible with the main scraper.
    """

    print("[LongCovidWeb] Fetching LongCovidWeb publications...")

    try:
        r = requests.get(LCWEB_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[LongCovidWeb] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # LongCovidWeb uses <li> or <div class="study-item"> blocks
    items = soup.select("li a[href], div.study-item a[href]")
    if not items:
        print("[LongCovidWeb] No publication items found.")
        return []

    for item in items[:max_results]:
        try:
            title = item.get_text(strip=True)
            url = item.get("href")

            if url and not url.startswith("http"):
                url = "https://longcovidweb.com" + url

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

                # Date (if present)
                date_tag = dsoup.find("time")
                if date_tag:
                    dt = date_tag.get("datetime") or date_tag.get_text(strip=True)
                    if dt:
                        try:
                            pub_date = datetime.strptime(dt[:10], "%Y-%m-%d")
                        except Exception:
                            pass

            except Exception as e:
                print(f"[LongCovidWeb] WARNING: Could not fetch detail page: {e}")

            paper_id = f"lcweb-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "longcovidweb",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[LongCovidWeb] ERROR parsing item: {e}")
            continue

    print(f"[LongCovidWeb] Parsed papers: {len(results)}")
    return results
