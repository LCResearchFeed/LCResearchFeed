import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------------------------------------------------
# PubMed: Fetch + Parse
# ---------------------------------------------------------

def log(msg: str):
    print(msg)


def _parse_pubmed_date(article) -> datetime:
    """
    Robust PubMed date parser.
    Supports:
        - <PubDate>
        - <ArticleDate>
        - <DateCreated>
        - <DateCompleted>
        - <DateRevised>
        - MedlineDate (text)
    """

    # 1. PubDate (preferred)
    pub = article.find("PubDate")
    if pub:
        y = pub.find("Year")
        m = pub.find("Month")
        d = pub.find("Day")
        if y:
            year = y.text
            month = m.text if m else "01"
            day = d.text if d else "01"
            try:
                return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
            except Exception:
                pass

    # 2. ArticleDate (ISO)
    ad = article.find("ArticleDate")
    if ad:
        raw = ad.text.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(raw[:len(fmt)], fmt)
            except Exception:
                pass

    # 3. MedlineDate (text like "2024 Feb 14")
    md = article.find("MedlineDate")
    if md:
        raw = md.text.strip()
        try:
            return datetime.strptime(raw, "%Y %b %d")
        except Exception:
            try:
                return datetime.strptime(raw, "%Y %b")
            except Exception:
                try:
                    return datetime.strptime(raw, "%Y")
                except Exception:
                    pass

    # 4. DateCreated
    dc = article.find("DateCreated")
    if dc:
        y = dc.find("Year")
        m = dc.find("Month")
        d = dc.find("Day")
        if y:
            try:
                return datetime.strptime(
                    f"{y.text}-{m.text}-{d.text}", "%Y-%m-%d"
                )
            except Exception:
                pass

    # 5. DateCompleted
    comp = article.find("DateCompleted")
    if comp:
        y = comp.find("Year")
        m = comp.find("Month")
        d = comp.find("Day")
        if y:
            try:
                return datetime.strptime(
                    f"{y.text}-{m.text}-{d.text}", "%Y-%m-%d"
                )
            except Exception:
                pass

    # 6. DateRevised
    rev = article.find("DateRevised")
    if rev:
        y = rev.find("Year")
        m = rev.find("Month")
        d = rev.find("Day")
        if y:
            try:
                return datetime.strptime(
                    f"{y.text}-{m.text}-{d.text}", "%Y-%m-%d"
                )
            except Exception:
                pass

    # Fallback
    return datetime.today()


def fetch_pubmed_pmids(max_results: int = 400) -> list[str]:
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

        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30, stream=True)
                r.raise_for_status()
                xml_text = r.content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(xml_text, "xml")
                break
            except Exception as e:
                log(f"[lc] PubMed batch retry {attempt+1}/3 failed: {e}")
                if attempt == 2:
                    continue

        for article in soup.find_all("PubmedArticle"):
            title = article.ArticleTitle.text if article.ArticleTitle else ""
            abstract = article.Abstract.text if article.Abstract else ""
            pmid = article.PMID.text if article.PMID else ""

            if not pmid or not title:
                continue

            mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

            pub_date = _parse_pubmed_date(article)

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


def fetch_pubmed_papers() -> list[dict]:
    pmids = fetch_pubmed_pmids()
    return fetch_pubmed_details(pmids)
