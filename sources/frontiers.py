import requests
from bs4 import BeautifulSoup
from datetime import datetime

def extract_frontiers_abstract(psoup):
    # 1. Standard abstract
    sec = psoup.find("section", {"class": "Abstract"})
    if sec:
        return sec.get_text(strip=True)

    # 2. Alternative abstract block
    div = psoup.find("div", {"class": "abstract"})
    if div:
        return div.get_text(strip=True)

    # 3. Summary section
    summ = psoup.find("section", {"class": "article-summary"})
    if summ:
        return summ.get_text(strip=True)

    # 4. First paragraph of article content
    body = psoup.find("section", {"class": "article-content"})
    if body:
        p = body.find("p")
        if p:
            return p.get_text(strip=True)

    return ""


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

            title_el = psoup.find("h1")
            title = title_el.get_text(strip=True) if title_el else ""

            abstract = extract_frontiers_abstract(psoup)

            date_el = psoup.find("time")
            if date_el and date_el.get("datetime"):
                try:
                    date = datetime.fromisoformat(date_el["datetime"])
                except:
                    date = None
            else:
                date = None

            p = {
                "id": full_url.split("/")[-2],
                "title": title,
                "abstract": abstract,
                "url": full_url,
                "source": "frontiers",
                "date": date,
            }

            papers.append(p)

        except Exception:
            continue

    return papers
