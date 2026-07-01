import requests
from bs4 import BeautifulSoup
from datetime import datetime

RECOVER_URL = "https://recovercovid.org/research/publications"

def fetch_recover_papers(max_results: int = 200) -> list[dict]:
    """
    Scrape RECOVER Long-Covid publications.
    Returns normalized dicts compatible with the main scraper.
    """

    print("[RECOVER] Fetching RECOVER publications...")

    try:
        r = requests.get(RECOVER_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[RECOVER] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # RECOVER uses <article> blocks for publications
    articles = soup.find_all("article")
    if not articles:
        print("[RECOVER] No articles found.")
        return []

    for a in articles[:max_results]:
        try:
            # Title
            title_tag = a.find("h3") or a.find("h2")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # URL
            link_tag = a.find("a", href=True)
            url = link_tag["href"] if link_tag else ""
            if url and not url.startswith("http"):
                url = "https://recovercovid.org" + url

            # Abstract/snippet
            snippet_tag = a.find("p")
            abstract = snippet_tag.get_text(strip=True) if snippet_tag else ""

            # Date
            date_obj = datetime.today()
            date_tag = a.find("time")
            if date_tag:
                dt = date_tag.get("datetime") or date_tag.get_text(strip=True)
                if dt:
                    try:
                        date_obj = datetime.strptime(dt[:10], "%Y-%m-%d")
                    except Exception:
                        pass

            # ID
            paper_id = f"recover-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "recover",
                    "mesh": [],
                    "date": date_obj,
                }
            )

        except Exception as e:
            print(f"[RECOVER] ERROR parsing article: {e}")
            continue

    print(f"[RECOVER] Parsed papers: {len(results)}")
    return results
