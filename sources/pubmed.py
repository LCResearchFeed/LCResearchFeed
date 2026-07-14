import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict


def log(msg: str):
    print(msg)


# ---------------------------------------------------------
# Universal date parser
# ---------------------------------------------------------
def parse_any_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None

    raw = raw.strip()

    iso_formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]

    for fmt in iso_formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass

    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except ValueError:
        pass

    try:
        return datetime.strptime(raw, "%Y-%m")
    except ValueError:
        pass

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

    if raw.lower().startswith("published:"):
        raw2 = raw.split(":", 1)[1].strip()
        parts2 = raw2.split()

        if len(parts2) == 2 and parts2[0] in text_months:
            try:
                return datetime(int(parts2[1]), text_months[parts2[0]], 1)
            except ValueError:
                pass

        if len(parts2) == 1 and parts2[0].isdigit():
            return datetime(int(parts2[0]), 1, 1)

    if len(parts) == 3 and parts[1] in text_months:
        try:
            return datetime(int(parts[2]), text_months[parts[1]], int(parts[0]))
        except ValueError:
            pass

    if len(parts) == 2 and parts[0] in text_months and parts[1].isdigit():
        try:
            return datetime(int(parts[1]), text_months[parts[0]], 1)
        except ValueError:
            pass

    if len(parts) == 2 and parts[1] in text_months:
        try:
            return datetime(int(parts[0]), text_months[parts[1]], 1)
        except ValueError:
            pass

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
        except ValueError:
            pass

    if "-" in raw:
        left = raw.split("-")[0].strip()
        parts_left = left.split()
        if len(parts_left) == 2 and parts_left[1] in seasons:
            try:
                return datetime(int(parts_left[0]), seasons[parts_left[1]], 1)
            except ValueError:
                pass

    import re
    match = re.search(r"\b(19|20)\d{2}\b", raw)
    if match:
        return datetime(int(match.group()), 1, 1)

    return None


# ---------------------------------------------------------
# PubMed date parser
# ---------------------------------------------------------
def parse_pubmed_date(article) -> Optional[datetime]:

    pub = article.find("PubDate")
    if pub:
        year_tag = pub.find("Year")
        month_tag = pub.find("Month")
        day_tag = pub.find("Day")

        if year_tag:
            raw = f"{year_tag.text.strip()} {month_tag.text.strip() if month_tag else '01'} {day_tag.text.strip() if day_tag else '01'}"
            parsed = parse_any_date(raw)
            if parsed:
                return parsed

    ad = article.find("ArticleDate")
    if ad:
        parsed = parse_any_date(ad.text.strip())
        if parsed:
            return parsed

    md = article.find("MedlineDate")
    if md:
        parsed = parse_any_date(md.text.strip())
        if parsed:
            return parsed

    def parse_three(tag):
        if not tag:
            return None
        year_tag = tag.find("Year")
        month_tag = tag.find("Month")
        day_tag = tag.find("Day")
        if year_tag and month_tag and day_tag:
            raw = f"{year_tag.text.strip()} {month_tag.text.strip()} {day_tag.text.strip()}"
            return parse_any_date(raw)
        return None

    for field in ["DateCreated", "DateCompleted", "DateRevised"]:
        parsed = parse_three(article.find(field))
        if parsed:
            return parsed

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
        "sort": "pub+date",
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        log(f"[PubMed] PMID fetch failed: {e}")
        return []

    return [p.split("</Id>")[0] for p in r.text.split("<Id>")[1:]]


# ---------------------------------------------------------
# Fetch details
# ---------------------------------------------------------
def fetch_pubmed_details(pmids: List[str]) -> List[Dict]:
    log("[PubMed] Fetching PubMed details…")
    if not pmids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    papers = []

    for i in range(0, len(pmids), 50):
        batch = pmids[i:i + 50]
        params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}

        soup = None
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30, stream=True)
                r.raise_for_status()
                xml_text = r.content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(xml_text, "xml")
                break
            except requests.exceptions.RequestException as e:
                log(f"[PubMed] Batch retry {attempt + 1}/3 failed: {e}")

        if soup is None:
            log("[PubMed] Failed to parse batch after 3 attempts")
            continue

        for article in soup.find_all("PubmedArticle"):
            pmid_tag = article.find("PMID")
            title_tag = article.find("ArticleTitle")

            if not pmid_tag or not title_tag:
                continue

            pmid = pmid_tag.text.strip()
            title = title_tag.text.strip()
            abstract = article.Abstract.text.strip() if article.Abstract else ""

            mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

            pub_date = parse_pubmed_date(article)
            if pub_date is None:
                log(f"[PubMed] Skipping paper without valid date: {title[:50]}")
                continue

            papers.append({
                "id": pmid,
                "title": title,
                "abstract": abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "source": "pubmed",
                "mesh": mesh_terms,
                "date": pub_date,
            })

    log(f"[PubMed] Parsed papers: {len(papers)}")
    return papers


def fetch_pubmed_papers() -> List[Dict]:
    pmids = fetch_pubmed_pmids()
    return fetch_pubmed_details(pmids)
