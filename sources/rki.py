import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://www.rki.de"
RKI_URL = f"{BASE_URL}/EN/Content/infections/COVID-19/Long_COVID/Long_COVID_node.html"

def fetch_rki_papers(max_results: int = 200) -> list[dict]:
    print("[RKI] Fetching RKI Long-Covid publications...")

    try:
        r = requests.get(RKI_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[RKI] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Nieuwe structuur: alle links staan in content-blokken
    items = soup.select("div.text a[href]")
    if not items:
        print("[RKI] No publication items found.")
        return []

    for item in items[:max_results]:
        try:
            title = item.get_text(strip=True)
            url = item.get("href")

            if not title or not url:
                continue

            # Relative → absolute
            if url.startswith("/"):
                url = BASE_URL + url

            # Abstract + datum uit detailpagina (indien HTML)
            abstract = ""
            pub_date = datetime.today()

            try:
                # PDF's kunnen niet geparsed worden → skip abstract
                if url.lower().endswith(".pdf"):
                    abstract = "PDF document (no abstract available)"
                else:
                    detail = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                    detail.raise_for_status()
                    dsoup = BeautifulSoup(detail.text, "html.parser")

                    # Abstract/snippet
                    ptag = dsoup.select_one("p")
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
