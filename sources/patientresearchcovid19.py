import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor


SCHOLAR_URL = "https://scholar.google.com/citations?user=rUDHZgIAAAAJ"
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/120 Safari/537.36"
    )
}

# Hard-coded fallback for PLRC papers that PubMed search struggles with
PLRC_MANUAL = {
    "Systematic review of the prevalence of long COVID": {
        "pmid": "38607861",
        "doi": "10.1016/j.jclinepi.2024.110012",
        "url": "https://pubmed.ncbi.nlm.nih.gov/38607861/",
        "journal": "Journal of Clinical Epidemiology",
        "date": datetime(2024, 4, 18),
        "mesh": ["COVID-19", "Post-Acute COVID-19 Syndrome", "Humans"],
        "authors": [],
        "abstract": "",
    }
}


def normalize_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower())


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def safe_xml(text: str):
    try:
        return ET.fromstring(text)
    except Exception:
        return None


def parse_date(article: ET.Element) -> datetime | None:
    """
    Universal PubMed-style date parser for PLRC.
    Supports:
    - ArticleDate (ISO)
    - PubMedPubDate (Year/Month/Day, including text months)
    - PubDate (Year/Month/Day or Year only)
    - MedlineDate ("2024 Feb 14", "2024 Feb", "2024", "2024 Oct", "2024 Fall")
    - DateCreated / DateCompleted / DateRevised
    """

    # -----------------------------
    # Universal parser
    # -----------------------------
    def parse_any(raw: str | None) -> datetime | None:
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

        # e.g. "14 July 2024"
        if len(parts) == 3 and parts[1] in text_months:
            try:
                return datetime(int(parts[2]), text_months[parts[1]], int(parts[0]))
            except Exception:
                pass

        # e.g. "2024 October"
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
    # ArticleDate
    # -----------------------------
    y = article.findtext(".//ArticleDate/Year")
    if y:
        raw = f"{y} {article.findtext('.//ArticleDate/Month','1')} {article.findtext('.//ArticleDate/Day','1')}"
        parsed = parse_any(raw)
        if parsed:
            return parsed

    # -----------------------------
    # PubMedPubDate
    # -----------------------------
    for tag in article.findall(".//PubMedPubDate"):
        y = tag.findtext("Year")
        m = tag.findtext("Month") or "1"
        d = tag.findtext("Day") or "1"
        raw = f"{y} {m} {d}"
        parsed = parse_any(raw)
        if parsed:
            return parsed

    # -----------------------------
    # PubDate
    # -----------------------------
    y = article.findtext(".//PubDate/Year")
    if y:
        m = article.findtext(".//PubDate/Month") or "1"
        d = article.findtext(".//PubDate/Day") or "1"
        raw = f"{y} {m} {d}"
        parsed = parse_any(raw)
        if parsed:
            return parsed

    # -----------------------------
    # MedlineDate
    # -----------------------------
    md = article.findtext(".//MedlineDate")
    if md:
        parsed = parse_any(md)
        if parsed:
            return parsed

    # -----------------------------
    # DateCreated / Completed / Revised
    # -----------------------------
    def parse_three(tag):
        if not tag:
            return None
        y = tag.findtext("Year")
        m = tag.findtext("Month")
        d = tag.findtext("Day")
        if y and m and d:
            raw = f"{y} {m} {d}"
            return parse_any(raw)
        return None

    for field in ["DateCreated", "DateCompleted", "DateRevised"]:
        parsed = parse_three(article.find(f".//{field}"))
        if parsed:
            return parsed

    return None



def pubmed_search_terms(title: str):
    """Two-stage search strategy."""
    return [
        f"{title} [Title]",
        f"{title} AND long covid",
        f"{title} AND post-acute covid",
        f"{title} AND PASC",
    ]


def fetch_pubmed_record(pmid: str):
    r = requests.get(
        PUBMED_FETCH_URL,
        params={"db": "pubmed", "id": pmid, "retmode": "xml"},
        headers=HEADERS,
        timeout=20,
    )
    return safe_xml(r.text)


def pubmed_lookup(title: str):
    # Hard-coded PLRC fix
    if title in PLRC_MANUAL:
        return PLRC_MANUAL[title].copy()

    empty = {
        "pmid": None,
        "abstract": "",
        "doi": None,
        "mesh": [],
        "date": None,
        "url": None,
        "authors": [],
        "journal": "",
    }

    pmids = []

    # Multi-strategy search
    for term in pubmed_search_terms(title):
        r = requests.get(
            PUBMED_SEARCH_URL,
            params={"db": "pubmed", "term": term, "retmax": 10, "retmode": "xml"},
            headers=HEADERS,
            timeout=20,
        )
        root = safe_xml(r.text)
        if root:
            pmids = [x.text for x in root.findall(".//Id")]
            if pmids:
                break

    if not pmids:
        return empty

    # Parallel fetch
    with ThreadPoolExecutor(max_workers=5) as exe:
        records = list(exe.map(fetch_pubmed_record, pmids))

    best = None
    best_score = 0.0

    for rec in records:
        if rec is None:
            continue

        pub_title = rec.findtext(".//ArticleTitle", "") or ""
        score = title_similarity(title, pub_title)

        # Heuristics
        mesh_terms = [
            x.text for x in rec.findall(".//MeshHeading/DescriptorName")
            if x is not None and x.text
        ]

        if any("Post-Acute COVID-19 Syndrome" in m for m in mesh_terms):
            score += 0.15

        if any(kw in pub_title.lower() for kw in ["long covid", "post covid", "pasc"]):
            score += 0.10

        if score > best_score:
            best_score = score
            best = rec

    if best is None or best_score < 0.75:
        print("[DEBUG] No reliable PubMed match:", title, "score:", round(best_score, 2))
        return empty

    pmid = best.findtext(".//PMID")

    abstract = " ".join(
        x.text for x in best.findall(".//AbstractText") if x is not None and x.text
    )

    doi = None
    for aid in best.findall(".//ArticleId"):
        if aid.attrib.get("IdType") == "doi":
            doi = aid.text

    mesh = [
        x.text for x in best.findall(".//MeshHeading/DescriptorName")
        if x is not None and x.text
    ]

    authors = []
    for author in best.findall(".//Author"):
        last = author.findtext("LastName")
        first = author.findtext("ForeName")
        if last:
            authors.append(f"{first or ''} {last}".strip())

    journal = best.findtext(".//Journal/Title", "") or ""
    date = parse_date(best)

    return {
        "pmid": pmid,
        "abstract": abstract,
        "doi": doi,
        "mesh": mesh,
        "date": date,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        "authors": authors,
        "journal": journal,
    }


def fetch_scholar_page(offset=0):
    r = requests.get(
        SCHOLAR_URL + f"&cstart={offset}",
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def fetch_plrc_papers(max_results=200):
    print("[PLRC] Fetching Google Scholar PLRC profile...")

    results = []
    seen = set()

    for offset in range(0, max_results, 20):
        print("[DEBUG] Scholar offset:", offset)
        soup = fetch_scholar_page(offset)
        items = soup.select("tr.gsc_a_tr")

        print("[DEBUG] Found:", len(items))
        if not items:
            break

        for item in items:
            if len(results) >= max_results:
                break

            title_el = item.select_one("a.gsc_a_at")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or title in seen:
                continue

            seen.add(title)
            print("[PLRC]", title)

            scholar_url = title_el.get("href") or ""
            if scholar_url.startswith("/"):
                scholar_url = "https://scholar.google.com" + scholar_url

            enriched = pubmed_lookup(title)
            pid = hashlib.md5(title.encode("utf-8")).hexdigest()[:12]

            results.append(
                {
                    "id": f"plrc-{pid}",
                    "title": title,
                    "abstract": enriched["abstract"],
                    "url": enriched["url"] or scholar_url,
                    "doi": enriched["doi"],
                    "pmid": enriched["pmid"],
                    "authors": enriched["authors"],
                    "journal": enriched["journal"],
                    "source": "plrc-scholar",
                    "mesh": enriched["mesh"],
                    "date": enriched["date"],
                }
            )

    print("[PLRC] Total papers:", len(results))
    return results

#if __name__ == "__main__":
#
#    papers = fetch_plrc_papers(
#        max_results=10
#    )
#
#
#    print(
#        "\nAantal papers:",
#        len(papers)
#    )
#
#
#    for p in papers:
#
#        print("=" * 80)
#        print("Titel :", p["title"])
#        print("Datum :", p["date"])
#        print("PMID  :", p["pmid"])
#        print("DOI   :", p["doi"])
#        print("Journal:", p["journal"])
#        print("URL   :", p["url"])
#        print("Mesh  :", p["mesh"][:5])