import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://patientresearchcovid19.com"
PAPERS_URL = f"{BASE_URL}/research/"

def fetch_plrc_papers(max_results: int = 200) -> list[dict]:
    print("[PLRC] Fetching Patient-Led Research Collaborative publications...")

    try:
        r = requests.get(PAPERS_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[PLRC] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Elke studie staat in <div class="post">
    items = soup.select("div.post")
    if not items:
        print("[PLRC] No publication items found.")
        return []

    for item in items[:max_results]:
        try:
            # Titel + link
            title_el = item.select_one("h2.entry-title a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href")

            if url and not url.startswith("http"):
                url = BASE_URL + url

            # Detailpagina ophalen
            abstract = ""
            pub_date = datetime.today()

            try:
                detail = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                detail.raise_for_status()
                dsoup = BeautifulSoup(detail.text, "html.parser")

                # Abstract/snippet
                content = dsoup.select_one("div.entry-content")
                if content:
                    abstract = " ".join(p.get_text(strip=True) for p in content.select("p"))

                # Datum
                date_tag = dsoup.select_one("time")
                if date_tag:
                    dt = date_tag.get("datetime") or date_tag.get_text(strip=True)
                    if dt:
                        try:
                            pub_date = datetime.strptime(dt[:10], "%Y-%m-%d")
                        except Exception:
                            pass

            except Exception as e:
                print(f"[PLRC] WARNING: Could not fetch detail page: {e}")

            paper_id = f"plrc-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "plrc",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[PLRC] ERROR parsing item: {e}")
            continue

    print(f"[PLRC] Parsed papers: {len(results)}")
    return results
