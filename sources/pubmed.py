import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------------------------------------------------
# PubMed: Fetch + Parse
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


def fetch_pubmed_details(pmids: list[str]) -> list[dict]:
    """
    Fetch full details for a list of PMIDs.
    Returns standardized paper dictionaries.
    """
    if not pmids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "xml")
    papers = []

    for article in soup.find_all("PubmedArticle"):
        title = article.ArticleTitle.text if article.ArticleTitle else ""
        abstract = article.Abstract.text if article.Abstract else ""
        pmid = article.PMID.text if article.PMID else ""

        if not pmid or not title:
            continue

        # MeSH terms
        mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

        # Publication date
        date_tag = article.find("PubDate")
        pub_date = datetime.today()

        if date_tag:
            y = date_tag.Year.text if date_tag.find("Year") else "2024"
            m = date_tag.Month.text if date_tag.find("Month") else "01"
            d = date_tag.Day.text if date_tag.find("Day") else "01"

            try:
                pub_date = datetime.strptime(f"{y}-{m}-{d}", "%Y-%m-%d")
            except Exception:
                pass

        papers.append({
            "id": pmid,
            "title": title.strip(),
            "abstract": abstract.strip(),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source": "pubmed",
            "mesh": mesh_terms,
            "date": pub_date,
        })

    return papers


def fetch_pubmed_papers() -> list[dict]:
    """
    Convenience wrapper used by lc_scraper.py.
    """
    pmids = fetch_pubmed_pmids()
    return fetch_pubmed_details(pmids)
