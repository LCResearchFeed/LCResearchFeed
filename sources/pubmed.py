import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict


# ---------------------------------------------------------
# Logging helper
# ---------------------------------------------------------
def log(msg: str):
    print(msg)


# ---------------------------------------------------------
# Robust PubMed date parser (NO fallback)
# ---------------------------------------------------------
def parse_pubmed_date(article) -> Optional[datetime]:
    """
    Parse PubMed XML date fields.
    Returns None if no valid date is found.
    Supports:
        - PubDate
        - ArticleDate (ISO)
        - MedlineDate ("2024 Feb 14", "2024 Feb", "2024")
        - DateCreated
        - DateCompleted
        - DateRevised
    """

    # 1. PubDate (preferred)
    pub = article.find("PubDate")
    if pub:
        y = pub.find("Year")
        m = pub.find("Month")
        d = pub.find("Day")
        if y:
            year = y.text.strip()
            month = (m.text.strip() if m else "01")
            day = (d.text.strip() if d else "01")
            try:
                return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
            except Exception:
                pass

    # 2. ArticleDate (ISO)
    ad = article.find("ArticleDate")
    if ad:
        raw = ad.text.strip()
        iso_formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in iso_formats:
            try:
                return datetime.strptime(raw[:len(fmt)], fmt)
            except Exception:
                pass

    # 3. MedlineDate ("2024 Feb 14", "2024 Feb", "2024")
    md = article.find("MedlineDate")
    if md:
        raw = md.text.strip()
        for fmt in ("%Y %b %d", "%Y %b", "%Y"):
            try:
                return datetime.strptime(raw, fmt)
            except Exception:
                pass

    # Helper for DateCreated / DateCompleted / DateRevised
    def parse_three(tag):
        if not tag:
            return None
        y = tag.find("Year")
        m = tag.find("Month")
        d = tag.find("Day")
        if y and m and d:
            try:
                return datetime.strptime(
                    f"{y.text.strip()}-{m.text.strip()}-{d.text.strip()}",
                    "%Y-%m-%d"
                )
            except Exception:
                return None
        return None

    # 4. DateCreated
    dc = parse_three(article.find("DateCreated"))
    if dc:
        return dc

    # 5. DateCompleted
    comp = parse_three(article.find("DateCompleted"))
    if comp:
        return comp

    # 6. DateRevised
    rev = parse_three(article.find("DateRevised"))
    if rev:
        return rev

    # No valid date found
    return None


# ---------------------------------------------------------
# Fetch PMIDs
# ---------------------------------------------------------
def fetch_pubmed_pmids(max_results: int = 400) -> List[str]:
    text_terms = [
        '"Long COVID"',
        '"Post-COVID"',
        '"Post COVID"',
        '"Post-acute sequelae"',
        '"Post-acute SARS-CoV-2"',
        '"Post COVID Condition"',
        '"PASC"',
        '"post-acute covid-19 syndrome"',
        '"post-covid-19 condition"',
        '"postviral fatigue syndrome"',
    ]

    mesh_terms = [
        '"Post-Acute COVID-19 Syndrome"[MeSH]',
        '"COVID-19"[MeSH] AND persistent',
        '"COVID-19"[MeSH] AND chronic',
        '"COVID-19"[MeSH] AND post-infectious',
    ]

    query = "(" + " OR ".join(text_terms + mesh_terms) + ")"

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "pub+date"
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    return [p.split("</Id>")[0] for p in r.text.split("<Id>")[1:]]


# ---------------------------------------------------------
# Fetch details
# ---------------------------------------------------------
def fetch_pubmed_details(pmids: List[str]) -> List[Dict]:
    log("[PubMed] Fetching PubMed details…")
    if not pmids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    BATCH_SIZE = 50
    papers = []

    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i:i+BATCH_SIZE]
        params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}

        # Retry mechanism
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30, stream=True)
                r.raise_for_status()
                xml_text = r.content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(xml_text, "xml")
                break
            except Exception as e:
                log(f"[PubMed] Batch retry {attempt+1}/3 failed: {e}")
                if attempt == 2:
                    continue

        for article in soup.find_all("PubmedArticle"):
            title = article.ArticleTitle.text if article.ArticleTitle else ""
            abstract = article.Abstract.text if article.Abstract else ""
            pmid = article.PMID.text if article.PMID else ""

            if not pmid or not title:
                continue

            mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

            pub_date = parse_pubmed_date(article)

            # Skip papers without valid date
            if pub_date is None:
                log(f"[PubMed] Skipping paper without valid date: {title[:50]}")
                continue

            papers.append(
                {
                    "id": pmid,
                    "title": title.strip(),
                    "abstract": abstract.strip(),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "source": "pubmed",
                    "mesh": mesh_terms,
                    "date": pub_date,
                }
            )

    log(f"[PubMed] Parsed papers: {len(papers)}")
    return papers


# ---------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------
def fetch_pubmed_papers() -> List[Dict]:
    pmids = fetch_pubmed_pmids()
    return fetch_pubmed_details(pmids)
