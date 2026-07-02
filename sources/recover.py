import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://recovercovid.org"
RECOVER_URL = f"{BASE_URL}/publications"

def fetch_recover_papers(max_results: int = 200) -> list[dict]:
    print("[RECOVER] Fetching RECOVER publications...")

    try:
        r = requests.get(RECOVER_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[RECOVER] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Nieuwe structuur: <div class="views-row">
    items = soup.select("div.views-row")
    if not items:
        print("[RECOVER] No publications found.")
        return []

    for item in items[:max_results]:
        try:
            # Titel
            title_el = item.select_one("h3 a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href")
            if url and not url.startswith("http"):
                url = BASE_URL + url

            # Abstract + datum uit detailpagina
            abstract = ""
            pub_date = datetime.today()

            try:
                detail = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                detail.raise_for_status()
                dsoup = BeautifulSoup(detail.text, "html.parser")

                # Abstract
                body = dsoup.select_one("div.field--name-body")
                if body:
                    abstract = body.get_text(strip=True)

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
                print(f"[RECOVER] WARNING: Could not fetch detail page: {e}")

            paper_id = f"recover-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "recover",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[RECOVER] ERROR parsing item: {e}")
            continue

    print(f"[RECOVER] Parsed papers: {len(results)}")
    return results
