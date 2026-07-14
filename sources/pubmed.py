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
    Robust PubMed date parser with support for:
    - PubDate (Year/Month/Day, including text months)
    - ArticleDate (ISO)
    - MedlineDate ("2024 Feb 14", "2024 Feb", "2024", "2024 Oct", "2024 Fall")
    - DateCreated / DateCompleted / DateRevised
    """

    # -----------------------------
    # Helper: universal date parser
    # -----------------------------
    def parse_any(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None

        raw = raw.strip()

        # ISO formats
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

        # YYYY-MM-DD
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d")
        except Exception:
            pass

        # YYYY-MM
        try:
            return datetime.strptime(raw, "%Y-%m")
        except Exception:
            pass

        # Text months
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
        if len(parts) == 2 and parts[1] in text_months:
            try:
                return datetime(int(parts[0]), text_months[parts[1]], 1)
            except Exception:
                pass

        # Seasons
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

        # YYYY only
        if len(raw) == 4 and raw.isdigit():
            try:
                return datetime.strptime(raw, "%Y")
            except Exception:
                pass

        return None

    # -----------------------------
    # 1. PubDate
    # -----------------------------
    pub = article.find("PubDate")
    if pub:
        y = pub.find("Year")
        m = pub.find("Month")
        d = pub.find("Day")

        if y:
            year = y.text.strip()
            month = m.text.strip() if m else "01"
            day = d.text.strip() if d else "01"

            # Month may be text ("Oct")
            raw = f"{year} {month} {day}"
            parsed = parse_any(raw)
            if parsed:
                return parsed

    # -----------------------------
    # 2. ArticleDate (ISO)
    # -----------------------------
    ad = article.find("ArticleDate")
    if ad:
        raw = ad.text.strip()
        parsed = parse_any(raw)
        if parsed:
            return parsed

    # -----------------------------
    # 3. MedlineDate
    # -----------------------------
    md = article.find("MedlineDate")
    if md:
        raw = md.text.strip()
        parsed = parse_any(raw)
        if parsed:
            return parsed

    # -----------------------------
    # Helper for DateCreated / Completed / Revised
    # -----------------------------
    def parse_three(tag):
        if not tag:
            return None
        y = tag.find("Year")
        m = tag.find("Month")
        d = tag.find("Day")
        if y and m and d:
            raw = f"{y.text.strip()} {m.text.strip()} {d.text.strip()}"
            return parse_any(raw)
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
