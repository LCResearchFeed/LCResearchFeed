import requests
from bs4 import BeautifulSoup
from datetime import datetime

def extract_frontiers_abstract(psoup):
    # 0. Meta abstract (beste en volledige bron)
    meta_abs = psoup.find("meta", {"name": "abstract"})
    if meta_abs and meta_abs.get("content"):
        return meta_abs["content"].strip()

    # 1. Meta description fallback
    meta = psoup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    og = psoup.find("meta", {"property": "og:description"})
    if og and og.get("content"):
        return og["content"].strip()

    # 2. Standard Frontiers abstract block
    sec = psoup.find("section", {"id": "abstract"})
    if sec:
        cont = sec.find("div", {"class": "content"})
        if cont:
            return cont.get_text(strip=True)

    # 3. JournalAbstract wrapper
    div = psoup.find("div", {"class": "JournalAbstract"})
    if div:
        return div.get_text(strip=True)

    # 4. Abstract container
    cont = psoup.find("div", {"class": "abstract-container"})
    if cont:
        return cont.get_text(strip=True)

    # 5. Generic article-section with Abstract header
    for sec in psoup.find_all("section", {"class": "article-section"}):
        h2 = sec.find("h2")
        if h2 and "abstract" in h2.get_text(strip=True).lower():
            cont = sec.find("div", {"class": "content"})
            if cont:
                return cont.get_text(strip=True)
            return sec.get_text(strip=True)

    # 6. Fallback: first paragraph
    p = psoup.find("p")
    if p:
        return p.get_text(strip=True)

    return ""


def extract_frontiers_date(psoup):
    # Datum uit Frontiers meta-tags
    metas = psoup.find_all("meta")

    pub_date_str = None
    online_date_str = None

    for m in metas:
        name = m.get("name")
        content = m.get("content")

        if not name or not content:
            continue

        if name == "citation_publication_date":
            pub_date_str = content.strip()

        if name == "citation_online_date":
            online_date_str = content.strip()

    # 1. Publication date (voorkeur)
    if pub_date_str:
        try:
            return datetime.strptime(pub_date_str, "%Y/%m/%d")
        except:
            pass

    # 2. Online date fallback
    if online_date_str:
        try:
            return datetime.strptime(online_date_str, "%Y/%m/%d")
        except:
            pass

    # 3. Oude fallback: <time datetime="...">
    date_el = psoup.find("time")
    if date_el and date_el.get("datetime"):
        try:
            return datetime.fromisoformat(date_el["datetime"])
        except:
            pass

    return None


def fetch_frontiers_papers():
    base_url = "https://www.frontiersin.org/journals/molecular-biosciences/articles"
    papers = []
    page = 1

    while True:
        params = {
            "tab": "latest",
            "sort": "latest",
            "page": page,
        }

        r = requests.get(base_url, params=params, timeout=20)
        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a", href=True)
        article_links = [
            l["href"] for l in links
            if "/articles/" in l["href"] and "/full" in l["href"]
        ]

        # Geen artikelen meer → stop paginatie
        if not article_links:
            break

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
                date = extract_frontiers_date(psoup)

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

        page += 1

    return papers


# if __name__ == "__main__":
    # papers = fetch_frontiers_papers()
    # print(f"Found {len(papers)} papers\n")

    # for p in papers:
        # print("ID:", p["id"])
        # print("Title:", p["title"])
        # print("Date:", p["date"].date() if p["date"] else None)
        # print("URL:", p["url"])
        # print("Abstract snippet:", p["abstract"][:300], "...")
        # print("-" * 80)
