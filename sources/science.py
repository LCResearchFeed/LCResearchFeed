import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------------------------------------------------
# Science.org: RSS scraping
# ---------------------------------------------------------

def fetch_science_papers(max_results: int = 50) -> list[dict]:
    """
    Scrape Science.org RSS feed for Long COVID.
    Returns standardized paper dictionaries.
    """

    url = "https://www.science.org/action/rss?AllField=long+covid"

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )
    except Exception:
        return []

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "xml")
    items = soup.find_all("item")

    results = []

    for item in items[:max_results]:
        title = (item.title.text or "").strip()
        link = (item.link.text or "").strip()
        summary = (item.description.text or "").strip() if item.description else ""

        # Parse publication date
        date_raw = (item.pubDate.text or "").strip() if item.pubDate else ""
        pub_date = datetime.today()

        # Science RSS uses formats like:
        # "Mon, 24 Jun 2024 00:00:00 GMT"
        # We try multiple formats.
        for fmt in ("%a, %d %b %Y", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d"):
            try:
                pub_date = datetime.strptime(date_raw[:len(fmt)], fmt)
                break
            except Exception:
                continue

        results.append({
            "id": link,
            "title": title,
            "abstract": summary,
            "url": link,
            "source": "science",
            "mesh": [],
            "date": pub_date,
        })

    return results
