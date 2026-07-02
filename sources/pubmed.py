import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils.date_normalizer import normalize_date

# ---------------------------------------------------------
# PubMed: Fetch + Parse
# ---------------------------------------------------------

def log(msg: str):
    print(msg)


# ---------------------------------------------------------
# FETCH PMIDs
# ---------------------------------------------------------

def fetch_pubmed_pmids(max_results: int = 400) -> list[str]:
    """
    Fetch PMIDs using a broad Long COVID query.
    """

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

    pmids = [p.split("</Id>")[0] for p in r.text.split("<Id>")[1:]]
    return pmids


# ---------------------------------------------------------
# PARSE PUBMED DETAILS
# ---------------------------------------------------------

def parse_pubmed_date(article) -> datetime | None:
    """
    PubMed dates are extremely inconsistent.
    Dit vangt ALLE varianten af en normaliseert naar datetime.
    """

    # 1. Try PubDate block
    date_tag = article.find("PubDate")
    if date_tag:
        year = date_tag.find("Year")
        month = date_tag.find("Month")
        day = date_tag.find("Day")

        y = year.text if year else None
        m = month.text if month else None
        d = day.text if day else None

        # PubMed months are often strings like "Jul"
        MONTH_MAP = {
            "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
            "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
            "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
        }

        if m in MONTH_MAP:
            m = MONTH_MAP[m]

        raw = "-".join([x for x in [y, m, d] if x])
        parsed = normalize_date(raw)
        if parsed:
            return parsed

    # 2. Try ArticleDate
    ad = article.find("ArticleDate")
    if ad:
        y = ad.find("Year").text if ad.find("Year") else None
        m = ad.find("Month").text if ad.find("Month") else None
        d = ad.find("Day").text if ad.find("Day") else None
        raw = "-".join([x for x in [y, m, d] if x])
        parsed = normalize_date(raw)
        if parsed:
            return parsed

    # 3. Try MedlineDate (free text)
    md = article.find("MedlineDate")
    if md:
        parsed = normalize_date(md.text)
        if parsed:
            return parsed

    # 4. Fallback: today
    return datetime.today()


def fetch_pubmed_details(pmids: list[str]) -> list[dict]:
    log("[lc] Fetching PubMed details…")
    if not pmids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    BATCH_SIZE = 50
    papers = []

    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i:i+BATCH_SIZE]
        params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}

        # retry mechanisme
        for attempt in range(3):
            try:
                r = requests.get(
                    url,
                    params=params,
                    timeout=30,
                    stream=True,
                )
                r.raise_for_status()

                xml_text = r.content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(xml_text, "xml")
                break

            except Exception as e:
                log(f"[lc] PubMed batch retry {attempt+1}/3 failed: {e}")
                if attempt == 2:
                    log("[lc] Skipping batch due to repeated failures.")
                    continue

        for article in soup.find_all("PubmedArticle"):
            title = article.ArticleTitle.text if article.ArticleTitle else ""
            abstract = article.Abstract.text if article.Abstract else ""
            pmid = article.PMID.text if article.PMID else ""

            if not pmid or not title:
                continue

            mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

            # ⭐ NEW: Perfect date parsing
            pub_date = parse_pubmed_date(article)

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

    log(f"[lc] Fetched PubMed papers: {len(papers)}")
    return papers


# ---------------------------------------------------------
# WRAPPER
# ---------------------------------------------------------

def fetch_pubmed_papers() -> list[dict]:
    pmids = fetch_pubmed_pmids()
    return fetch_pubmed_details(pmids)
