import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://patientresearchcovid19.com"
PRC_URL = f"{BASE_URL}/research/"

def fetch_patientresearchcovid19_papers(max_results: int = 200) -> list[dict]:
    print("[PatientResearch] Fetching Patient Led Research Collaborative publications...")

    try:
        r = requests.get(PRC_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[PatientResearch] ERROR fetching page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Elke publicatie staat in <div class="post">
    posts = soup.select("div.post")
    if not posts:
        print("[PatientResearch] No publication items found.")
        return []

    for post in posts[:max_results]:
        try:
            # Titel
            title_el = post.select_one("h2.entry-title a")
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

                # Abstract
                body = dsoup.select_one("div.entry-content")
                if body:
                    abstract = body.get_text(strip=True)

                # Datum
                time_tag = dsoup.find("time")
                if time_tag:
                    dt = time_tag.get("datetime") or time_tag.get_text(strip=True)
                    if dt:
                        try:
                            pub_date = datetime.strptime(dt[:10], "%Y-%m-%d")
                        except Exception:
                            pass

            except Exception as e:
                print(f"[PatientResearch] WARNING: Could not fetch detail page: {e}")

            paper_id = f"patientresearch-{title[:40].replace(' ', '-')}".lower()

            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": url,
                    "source": "patientresearchcovid19",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[PatientResearch] ERROR parsing item: {e}")
            continue

    print(f"[PatientResearch] Parsed papers: {len(results)}")
    return results
