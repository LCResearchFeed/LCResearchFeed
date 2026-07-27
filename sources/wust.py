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
    for key in ("firstPublicationDate", "epubDate"):
        d = item.get(key)
        if d:
            try:
                return datetime.strptime(d, "%Y-%m-%d")
            except:
                pass

    year = item.get("pubYear")
    if year:
        try:
            return datetime.strptime(str(year), "%Y")
        except:
            pass

    return None


def _extract_url(item: dict):
    urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
    if urls:
        for u in urls:
            if "url" in u:
                return u["url"]

    pmcid = item.get("pmcid")
    if pmcid:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"

    doi = item.get("doi")
    if doi:
        return f"https://doi.org/{doi}"

    return None


def _build_id(item: dict, title: str):
    """
    Nieuwe, stabiele ID-logica:
    - Als er een PMID is → gebruik PMID
    - Als er een PMC is → gebruik PMC
    - Als er een DOI is → gebruik doi-<doi>
    - Anders → fallback op titel
    """

    pmid = item.get("pmid")
    if pmid:
        return pmid  # pure PMID

    pmcid = item.get("pmcid")
    if pmcid:
        return f"PMC{pmcid}"

    doi = item.get("doi")
    if doi:
        return f"doi-{doi}"

    # fallback: stabiele titel-ID
    safe_title = title[:60].replace(" ", "_")
    return f"wust-{safe_title}"


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
            "category": "mechanism",
            "date": date,
        })

    print(f"[Wust] Found {len(results)} LC papers from Rob Wüst.")
    return results
