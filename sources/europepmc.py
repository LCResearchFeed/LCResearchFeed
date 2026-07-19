import requests
from datetime import datetime
from typing import Optional, List, Dict

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


# ---------------------------------------------------------
# Robust EuropePMC date parser (NO fallback to today)
# ---------------------------------------------------------
def parse_europepmc_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None

    raw = raw.strip()

    # ----------------------------------------
    # ISO formats
    # ----------------------------------------
    iso_formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in iso_formats:
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            pass

    # ----------------------------------------
    # YYYY-MM-DD
    # ----------------------------------------
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        pass

    # ----------------------------------------
    # YYYY-MM
    # ----------------------------------------
    try:
        return datetime.strptime(raw, "%Y-%m")
    except Exception:
        pass

    # ----------------------------------------
    # Text months
    # ----------------------------------------
    text_months = {
        "Jan": 1, "January": 1,
        "Feb": 2, "February": 2,
        "Mar": 3, "March": 3,
        "Apr": 4, "April": 4,
        "May": 5,
        "Jun": 6, "June": 6,
        "Jul": 7, "July": 7,
        "Aug": 8, "August": 8,
        "Sep": 9, "Sept": 9, "September": 9,
        "Oct": 10, "October": 10,
        "Nov": 11, "November": 11,
        "Dec": 12, "December": 12,
    }

    parts = raw.split()

    # ----------------------------------------
    # "Published: July 2024"
    # ----------------------------------------
    if raw.lower().startswith("published:"):
        raw2 = raw.split(":", 1)[1].strip()
        parts2 = raw2.split()
        if len(parts2) == 2 and parts2[0] in text_months:
            try:
                return datetime(int(parts2[1]), text_months[parts2[0]], 1)
            except Exception:
                pass
        if len(parts2) == 1 and parts2[0].isdigit():
            return datetime(int(parts2[0]), 1, 1)

    # ----------------------------------------
    # "14 July 2024"
    # ----------------------------------------
    if len(parts) == 3 and parts[1] in text_months:
        try:
            return datetime(int(parts[2]), text_months[parts[1]], int(parts[0]))
        except Exception:
            pass

    # ----------------------------------------
    # "2024 July"
    # ----------------------------------------
    if len(parts) == 2 and parts[1] in text_months:
        try:
            return datetime(int(parts[0]), text_months[parts[1]], 1)
        except Exception:
            pass

    # ----------------------------------------
    # Seasons
    # ----------------------------------------
    seasons = {
        "Winter": 1,
        "Spring": 3,
        "Summer": 6,
        "Autumn": 9,
        "Fall": 9,
    }

    if len(parts) == 2 and parts[1] in seasons:
        try:
            return datetime(int(parts[0]), seasons[parts[1]], 1)
        except Exception:
            pass

    # ----------------------------------------
    # Ranges: "2024 Fall-Winter"
    # ----------------------------------------
    if "-" in raw:
        left = raw.split("-")[0].strip()
        parts_left = left.split()
        if len(parts_left) == 2 and parts_left[1] in seasons:
            try:
                return datetime(int(parts_left[0]), seasons[parts_left[1]], 1)
            except Exception:
                pass

    # ----------------------------------------
    # Extract ANY year → ALWAYS 01-01-YYYY
    # ----------------------------------------
    import re
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    if m:
        year = int(m.group())
        return datetime(year, 1, 1)

    return None

# ---------------------------------------------------------
# Main fetcher
# ---------------------------------------------------------
def fetch_europepmc_papers(max_results: int = 200) -> List[Dict]:
    print("[EuropePMC] Fetching EuropePMC papers...")

    query = 'LONG COVID OR "post-acute sequelae" OR PASC'
    params = {
        "query": query,
        "format": "json",
        "pageSize": max_results,
    }

    try:
        r = requests.get(API_URL, params=params, timeout=45)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[EuropePMC] ERROR fetching data: {e}")
        return []

    results = []
    items = data.get("resultList", {}).get("result", [])

    for item in items:
        try:
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstractText") or "").strip()

            pmcid = item.get("pmcid")
            doi = item.get("doi")
            pmid = item.get("pmid")

            # -----------------------------
            # URL extraction
            # -----------------------------
            link = None
            full_urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])

            # 1. Full-text URLs (als ze bestaan)
            if full_urls:
                link = full_urls[0].get("url", "")

            # 2. PMC fallback (belangrijk!)
            elif pmcid:
                link = f"https://europepmc.org/article/PMC/{pmcid}"

            # 3. PubMed fallback
            elif pmid:
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            # 4. DOI fallback
            elif doi:
                link = f"https://doi.org/{doi}"

            # 5. Skip alleen als er *echt* geen link is
            if not link:
                print(f"[EuropePMC] Skipping paper without valid link: {title[:50]}")
                continue

            # -----------------------------
            # DATE extraction (no fallback)
            # -----------------------------
            raw_date = (
                item.get("firstPublicationDate")
                or item.get("pubDate")
                or item.get("pubYear")
            )

            pub_date = parse_europepmc_date(raw_date)

            if pub_date is None:
                print(f"[EuropePMC] Skipping paper without valid date: {title[:50]}")
                continue

            # -----------------------------
            # ID construction
            # -----------------------------
            if doi:
                paper_id = f"europepmc-{doi}"
            elif pmid:
                paper_id = f"europepmc-{pmid}"
            else:
                safe_title = title[:40].replace(" ", "_")
                paper_id = f"europepmc-{safe_title}"

            # -----------------------------
            # Build paper dict
            # -----------------------------
            results.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "url": link,
                    "source": "europepmc",
                    "mesh": [],
                    "date": pub_date,
                }
            )

        except Exception as e:
            print(f"[EuropePMC] ERROR parsing item: {e}")
            continue


    print(f"[EuropePMC] Parsed papers: {len(results)}")
    return results

# if __name__ == "__main__":
    # papers = fetch_europepmc_papers()

    # print(f"\nTotal papers: {len(papers)}")

    # for p in papers:
        # print("ID:", p["id"])
        # print("Title:", p["title"])
        # print("Date:", p["date"].date() if p["date"] else None)
        # print("URL:", p["url"])
        # print("Abstract snippet:", p["abstract"][:200], "...")
        # print("-" * 80)