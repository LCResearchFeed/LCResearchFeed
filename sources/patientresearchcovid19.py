import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
import time
import random
from typing import Optional, List, Dict


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
SCHOLAR_URL = "https://scholar.google.com/citations?user=rUDHZgIAAAAJ"
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
]

HEADERS = {
    "User-Agent": random.choice(UA_LIST)
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


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def normalize_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower())


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def safe_xml(text: str):
    try:
        return ET.fromstring(text)
    except Exception:
        return None


# ---------------------------------------------------------
# Universele datumparser
# ---------------------------------------------------------
def parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None

    raw = raw.strip()

    # 1. ISO formats
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

    # 2. YYYY-MM-DD
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        pass

    # 3. YYYY-MM
    try:
        return datetime.strptime(raw, "%Y-%m")
    except Exception:
        pass

    # 4. Text months
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

    # 5. "Published: July 2024"
    if raw.lower().startswith("published:"):
        raw2 = raw.split(":", 1)[1].strip()
        parts2 = raw2.split()

        if len(parts2) == 2 and parts2[0] in text_months:
            try:
                return datetime(int(parts2[1]), text_months[parts2[0]], 1)
            except Exception:
                pass

        if len(parts2) == 1 and parts2[0].isdigit():
            return datetime(int(parts2[0]), 1, 1)

    # 6. "14 July 2024"
    if len(parts) == 3 and parts[1] in text_months:
        try:
            return datetime(int(parts[2]), text_months[parts[1]], int(parts[0]))
        except Exception:
            pass

    # 7. "July 2024"
    if len(parts) == 2 and parts[0] in text_months and parts[1].isdigit():
        try:
            return datetime(int(parts[1]), text_months[parts[0]], 1)
        except Exception:
            pass

    # 8. "2024 July"
    if len(parts) == 2 and parts[1] in text_months:
        try:
            return datetime(int(parts[0]), text_months[parts[1]], 1)
        except Exception:
            pass

    # 9. Seasons
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

    # 10. Ranges: "2024 Fall-Winter"
    if "-" in raw:
        left = raw.split("-")[0].strip()
        parts_left = left.split()
        if len(parts_left) == 2 and parts_left[1] in seasons:
            try:
                return datetime(int(parts_left[0]), seasons[parts_left[1]], 1)
            except Exception:
                pass

    # 11. ANY year → 01-01-YYYY
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    if m:
        year = int(m.group())
        return datetime(year, 1, 1)

    return None


# ---------------------------------------------------------
# PubMed lookup
# ---------------------------------------------------------
def pubmed_search_terms(title: str) -> List[str]:
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


def pubmed_lookup(title: str) -> Dict:
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

    pmids: List[str] = []

    # Multi-strategy search
    for term in pubmed_search_terms(title):
        try:
            r = requests.get(
                PUBMED_SEARCH_URL,
                params={"db": "pubmed", "term": term, "retmax": 10, "retmode": "xml"},
                headers=HEADERS,
                timeout=20,
            )
        except Exception as e:
            print("[PLRC] PubMed search error:", e)
            continue

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
        print("[PLRC] No reliable PubMed match:", title, "score:", round(best_score, 2))
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

    # Datum uit PubMed
    # Gebruik dezelfde universele parser op MedlineDate / PubDate / ArticleDate
    date_raw = (
        best.findtext(".//PubDate/Year")
        or best.findtext(".//ArticleDate")
        or best.findtext(".//MedlineDate")
    )
    date = parse_date(date_raw) if date_raw else None

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


# ---------------------------------------------------------
# Google Scholar fetch
# ---------------------------------------------------------
def fetch_scholar_page(offset: int = 0) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(
            SCHOLAR_URL + f"&cstart={offset}",
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
    except Exception as e:
        print("[PLRC] Scholar request error:", e)
        return None

    if "/sorry/" in r.text.lower():
        print("[PLRC] BLOCKED BY GOOGLE SCHOLAR CAPTCHA")
        return None

    return BeautifulSoup(r.text, "html.parser")


# ---------------------------------------------------------
# Main PLRC fetcher
# ---------------------------------------------------------
def fetch_plrc_papers(max_results: int = 200) -> List[Dict]:
    print("[PLRC] Fetching Google Scholar PLRC profile...")

    results: List[Dict] = []
    seen = set()

    for offset in range(0, max_results, 20):
        print("[DEBUG] Scholar offset:", offset)
        soup = fetch_scholar_page(offset)
        if soup is None:
            print("[PLRC] Stopping PLRC fetch due to Scholar error/block.")
            break

        items = soup.select("tr.gsc_a_tr") or []
        print("[DEBUG] Found:", len(items))

        if not items:
            print("[PLRC] No items returned — likely end of list or block.")
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

        # kleine pauze om Scholar niet te triggeren
        time.sleep(1.5)

    print("[PLRC] Total papers:", len(results))
    return results
