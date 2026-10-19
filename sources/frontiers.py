import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def extract_frontiers_abstract(psoup):
    meta_abs = psoup.find("meta", {"name": "abstract"})
    if meta_abs and meta_abs.get("content"):
        return meta_abs["content"].strip()

    meta = psoup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    og = psoup.find("meta", {"property": "og:description"})
    if og and og.get("content"):
        return og["content"].strip()

    sec = psoup.find("section", {"id": "abstract"})
    if sec:
        cont = sec.find("div", {"class": "content"})
        if cont:
            return cont.get_text(strip=True)

    div = psoup.find("div", {"class": "JournalAbstract"})
    if div:
        return div.get_text(strip=True)

    cont = psoup.find("div", {"class": "abstract-container"})
    if cont:
        return cont.get_text(strip=True)

    for sec in psoup.find_all("section", {"class": "article-section"}):
        h2 = sec.find("h2")
        if h2 and "abstract" in h2.get_text(strip=True).lower():
            cont = sec.find("div", {"class": "content"})
            if cont:
                return cont.get_text(strip=True)
            return sec.get_text(strip=True)

    p = psoup.find("p")
    if p:
        return p.get_text(strip=True)

    return ""


def extract_frontiers_date(psoup):
    metas = psoup.find_all("meta")
    pub_date_str = None
    online_date_str = None

    for m in metas:
        name = m.get("name")
        content = m.get("content")

        if not name or not content:
            continue

        if name == "citation_publication_date" and isinstance(content, str):
            pub_date_str = content.strip()

        if name == "citation_online_date" and isinstance(content, str):
            online_date_str = content.strip()

    for candidate in (pub_date_str, online_date_str):
        if isinstance(candidate, str):
            try:
                return datetime.strptime(candidate, "%Y/%m/%d")
            except:
                pass

    date_el = psoup.find("time")
    if date_el:
        dt = date_el.get("datetime")
        if isinstance(dt, str):
            try:
                return datetime.fromisoformat(dt)
            except:
                pass

    return None




def request_with_retries(url, params=None, attempts=3):
    """Voer een HTTP-aanvraag uit met retries bij tijdelijke fouten."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LC-Scraper/1.0)"
    }

    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=(10, 60),
            )

            # Tijdelijke serverfouten en rate limits opnieuw proberen.
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < attempts:
                    wait = 5 * attempt
                    print(
                        f"[Frontiers] HTTP {response.status_code}; "
                        f"retry {attempt}/{attempts} in {wait}s"
                    )
                    response.close()
                    time.sleep(wait)
                    continue

            return response

        except requests.exceptions.RequestException as e:
            if attempt == attempts:
                print(
                    f"[Frontiers] Request failed after "
                    f"{attempts} attempts: {url} ({e})"
                )
                return None

            wait = 5 * attempt
            print(
                f"[Frontiers] Request error; "
                f"retry {attempt}/{attempts} in {wait}s: {e}"
            )
            time.sleep(wait)

    return None


def fetch_article(link):
    full_url = (
        link if link.startswith("http")
        else "https://www.frontiersin.org" + link
    )

    try:
        pr = request_with_retries(full_url)

        if pr is None:
            return None

        try:
            if pr.status_code != 200:
                print(
                    f"[Frontiers] Article returned "
                    f"HTTP {pr.status_code}: {full_url}"
                )
                return None

            psoup = BeautifulSoup(pr.text, "html.parser")
        finally:
            pr.close()

        title_el = psoup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        if not title:
            return None

        abstract = extract_frontiers_abstract(psoup)
        date = extract_frontiers_date(psoup)

        parts = full_url.rstrip("/").split("/")
        paper_id = parts[-1] if parts[-1] != "full" else parts[-2]

        return {
            "id": paper_id,
            "title": title,
            "abstract": abstract,
            "url": full_url,
            "source": "frontiers",
            "date": date,
        }

    except Exception as e:
        print(f"[Frontiers] Article parsing failed: {full_url}: {e}")
        return None


def fetch_frontiers_papers(max_pages=10, stop_before_year=2025):
    base_url = "https://www.frontiersin.org/articles"

    papers = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        print(f"[Frontiers] Fetching page {page}...")

        params = {
            "query": "covid",
            "search": "covid",
            "sort": 1,
            "page": page,
        }

        r = request_with_retries(base_url, params=params)

        # Een mislukte pagina mag de rest van de pipeline niet afbreken.
        if r is None:
            print(
                f"[Frontiers] Page {page} failed after retries. "
                f"Keeping {len(papers)} papers already collected."
            )
            break

        try:
            if r.status_code != 200:
                print(
                    f"[Frontiers] Page {page} returned "
                    f"HTTP {r.status_code}, stopping."
                )
                break

            soup = BeautifulSoup(r.text, "html.parser")
        finally:
            r.close()

        links = soup.select("a[href*='/articles/']")

        article_links = list(dict.fromkeys(
            a["href"]
            for a in links
            if a.get("href")
            and "/articles/" in a["href"]
            and a["href"].count("/") > 3
        ))

        if not article_links:
            print(
                f"[Frontiers] No articles found on page {page}, stopping."
            )
            break

        results = []

        # Een lager aantal gelijktijdige verzoeken belast de website minder.
        with ThreadPoolExecutor(max_workers=5) as exe:
            futures = [
                exe.submit(fetch_article, link)
                for link in article_links
            ]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"[Frontiers] Worker failed: {e}")

        new_count = 0
        stop_for_old_paper = False

        for paper in results:
            if paper["id"] in seen_ids:
                continue

            if (
                paper["date"]
                and paper["date"].year < stop_before_year
            ):
                print(
                    f"[Frontiers] Found paper before "
                    f"{stop_before_year}: {paper['title']}"
                )
                stop_for_old_paper = True
                continue

            seen_ids.add(paper["id"])
            papers.append(paper)
            new_count += 1

        print(
            f"[Frontiers] Page {page}: {new_count} new papers "
            f"(total: {len(papers)})"
        )

        if stop_for_old_paper:
            print("[Frontiers] Stopping at the year cutoff.")
            break

        if new_count == 0:
            print("[Frontiers] No new papers on this page, stopping.")
            break

    print(f"[Frontiers] Finished with {len(papers)} papers.")
    return papers



# if __name__ == "__main__":
    # papers, last_page = fetch_frontiers_papers(max_pages=10, stop_before_year=2025)

    # print(f"\nTotal papers: {len(papers)}")
    # print(f"Last page scraped: {last_page}\n")

    # for p in papers:
        # print("ID:", p["id"])
        # print("Title:", p["title"])
        # print("Date:", p["date"].date() if p["date"] else None)
        # print("URL:", p["url"])
        # print("Abstract snippet:", p["abstract"][:200], "...")
        # print("-" * 80)
