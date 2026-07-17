import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_frontiers_papers():
    url = "https://www.frontiersin.org/articles"
    papers = []

    # 1. Zoekpagina ophalen
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return papers

    soup = BeautifulSoup(r.text, "html.parser")

    # 2. Vind alle artikel-links
    links = soup.find_all("a", href=True)
    article_links = [
        l["href"] for l in links
        if "/articles/" in l["href"] and "/full" in l["href"]
    ]

    for link in article_links:
        full_url = link if link.startswith("http") else "https://www.frontiersin.org" + link

        try:
            pr = requests.get(full_url, timeout=20)
            if pr.status_code != 200:
                continue

            psoup = BeautifulSoup(pr.text, "html.parser")

            title = psoup.find("h1")
            abstract = psoup.find("section", {"class": "Abstract"})
            date = psoup.find("time")

            p = {
                "id": full_url.split("/")[-2],
                "title": title.text.strip() if title else "",
                "abstract": abstract.text.strip() if abstract else "",
                "url": full_url,
                "source": "frontiers",
                "date": datetime.fromisoformat(date["datetime"]) if date else None,
            }

            papers.append(p)

        except Exception:
            continue

    return papers
