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


def parse_date(article: ET.Element):
    # ArticleDate
    y = article.findtext(".//ArticleDate/Year")
    if y:
        try:
            return datetime(
                int(y),
                int(article.findtext(".//ArticleDate/Month", "1")),
                int(article.findtext(".//ArticleDate/Day", "1")),
            )
        except Exception:
            pass

    # PubMedPubDate
    for tag in article.findall(".//PubMedPubDate"):
        y = tag.findtext("Year")
        if y:
            try:
                return datetime(
                    int(y),
                    int(tag.findtext("Month") or 1),
                    int(tag.findtext("Day") or 1),
                )
            except Exception:
                pass

    # PubDate
    y = article.findtext(".//PubDate/Year")
    if y:
        try:
            return datetime(int(y), 1, 1)
        except Exception:
            pass

    # MedlineDate
    md = article.findtext(".//MedlineDate")
    if md:
        m = re.search(r"\d{4}", md)
        if m:
            try:
                return datetime(int(m.group()), 1, 1)
            except Exception:
                pass

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