import requests
from datetime import datetime

# ---------------------------------------------------------
# EuropePMC query voor ALLE Rob Wüst Long-Covid papers
# ---------------------------------------------------------
WUST_QUERY = (
    'AUTH:"Wust R" AND (long covid OR long-covid OR PASC OR '
    'post-acute OR post covid OR post-viral OR SARS-CoV-2 OR '
    'post-COVID OR post-COVID-19 OR PCC)'
)

URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    f"?query={WUST_QUERY}&format=json&pageSize=200"
)

LC_TERMS = [
    "long covid", "long-covid", "pasc", "post-acute",
    "post covid", "post-viral", "sars-cov-2",
    "post-covid", "post-covid-19", "pcc"
]


def _contains_lc_terms(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in LC_TERMS)


def _parse_date(item: dict):
    """
    EuropePMC heeft meerdere datumvelden:
    - firstPublicationDate
    - epubDate
    - pubYear (alleen jaar)
    """
    for key in ("firstPublicationDate", "epubDate"):
        d = item.get(key)
        if d:
            try:
                return datetime.strptime(d, "%Y-%m-%d")
            except:
                pass

    # fallback: alleen jaar
    year = item.get("pubYear")
    if year:
        try:
            return datetime.strptime(str(year), "%Y")
        except:
            pass

    return None


def _extract_url(item: dict):
    """
    EuropePMC geeft soms meerdere full-text URLs.
    Als die ontbreken:
    - PMC fallback
    - DOI fallback
    """
    urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
    if urls:
        for u in urls:
            if "url" in u:
                return u["url"]

    # PMC fallback
    pmcid = item.get("pmcid")
    if pmcid:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"

    # DOI fallback
    doi = item.get("doi")
    if doi:
        return f"https://doi.org/{doi}"

    return None


def _build_id(item: dict, title: str):
    """
    Robuuste ID:
    - EuropePMC ID
    - DOI
    - Titel fallback
    """
    if item.get("id"):
        return f"wust-{item['id']}"

    if item.get("doi"):
        return f"wust-{item['doi']}"

    return f"wust-{title[:60].replace(' ', '_')}"


# ---------------------------------------------------------
# Main fetcher
# ---------------------------------------------------------
def fetch_wust_papers():
    print("[Wust] Fetching Rob Wüst Long-Covid papers via EuropePMC...")

    r = requests.get(URL)
    data = r.json()

    results = []

    for item in data.get("resultList", {}).get("result", []):
        title = item.get("title", "")
        abstract = item.get("abstractText", "")

        combo = f"{title} {abstract}".lower()

        # Extra LC-veiligheidsfilter
        if not _contains_lc_terms(combo):
            continue

        url = _extract_url(item)
        date = _parse_date(item)
        doi = item.get("doi")

        paper_id = _build_id(item, title)

        results.append({
            "id": paper_id,
            "title": title,
            "abstract": abstract,
            "url": url,
            "doi": doi,
            "source": "wust",
            "category": "mechanism",  # jouw AI-classifier bepaalt later de echte categorie
            "date": date,
        })

    print(f"[Wust] Found {len(results)} LC papers from Rob Wüst.")
    return results


# if __name__ == "__main__":
    # papers = fetch_wust_papers()
    # for p in papers:
        # print(p["title"])
