import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import requests
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
SEEN_FILE = "posted_pmids.txt"
REPO_PATH = REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
INDEX_FILE = os.path.join(REPO_PATH, "index.html")
BASE_NATURE = "https://www.nature.com"

# ---------------------------------------------------------
# Long Covid kerntermen
# ---------------------------------------------------------
LC_TERMS = [
    "long covid", "post covid", "post-covid", "post acute covid",
    "post-acute covid", "post covid condition", "post-covid condition",
    "post-acute sequelae", "pasc", "post-acute sars-cov-2"
]

LC_MESH = [
    "long covid", "post-acute covid-19 syndrome", "post-covid-19 condition",
    "post-acute sequelae of sars-cov-2 infection", "postviral fatigue syndrome"
]

MECHANISM_TERMS = [
    "mechanism", "pathophysiology", "pathogenesis", "immune", "immunological",
    "autoantibodies", "autoimmunity", "inflammation", "neuroinflammation",
    "endothelium", "endothelial", "microclots", "coagulation", "mitochondria",
    "mitochondrial", "metabolic", "metabolism", "viral persistence",
    "persistent virus", "reactivation", "herpesvirus", "ebv", "cmv",
    "autonomic", "dysautonomia", "pots", "neurological", "brain", "neuro"
]

TREATMENT_TERMS = [
    "treatment", "therapy", "therapeutic", "intervention", "clinical trial",
    "phase", "randomized", "randomised", "rehabilitation", "vagus nerve",
    "vagus nerve stimulation", "vns", "immunomodulation", "antiviral", "drug",
    "pharmacological", "exercise therapy", "pacing", "rehab", "protocol",
    "improvement", "recovery"
]

NOISE_TERMS = [
    "lung function", "exercise tolerance", "spirometer", "spirometry",
    "rehabilitation programme", "rehabilitation", "rehab", "balance",
    "telerehab", "telerehabilitation", "mixed-methods", "survey",
    "cohort study", "cohort", "psychosocial", "healthcare utilization",
    "post covid morbidity", "persistent symptoms", "chronic morbidity",
    "follow-up", "dnam", "epigenetic", "fitness", "dyspnea",
    "functional status", "workforce exit", "work productivity",
    "care pathways", "quality of life", "burden",
    "protocol for a multicentre clinical trial", "study protocol"
]

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in seen:
            f.write(item + "\n")

# ---------------------------------------------------------
# Filters
# ---------------------------------------------------------
def is_strict_long_covid(p):
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()
    return any(kw in t or kw in a for kw in LC_TERMS)

def has_mesh_long_covid(p):
    return any(term.lower() in p.get("mesh", []) for term in LC_MESH)

def is_mechanism_or_treatment(p):
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()
    mech = any(kw in t or kw in a for kw in MECHANISM_TERMS)
    treat = any(kw in t or kw in a for kw in TREATMENT_TERMS)
    return mech or treat

def is_noise(p):
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()
    return any(kw in t or kw in a for kw in NOISE_TERMS)

def is_valid_lc_mechanism_paper(p):
    if not is_strict_long_covid(p):
        return False
    if p["source"] == "pubmed" and not has_mesh_long_covid(p):
        return False
    if not is_mechanism_or_treatment(p):
        return False
    return True

def relevance_score(p):
    score = 0
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()

    if is_strict_long_covid(p): score += 3
    if p["source"] == "pubmed" and has_mesh_long_covid(p): score += 3
    if any(kw in t or kw in a for kw in MECHANISM_TERMS): score += 2
    if any(kw in t or kw in a for kw in TREATMENT_TERMS): score += 2
    if len(a) > 400: score += 1
    if p["source"] == "nature": score += 1
    if is_noise(p): score -= 2

    return score

# ---------------------------------------------------------
# PubMed
# ---------------------------------------------------------
def fetch_pubmed_pmids(max_results=200):
    query = " OR ".join([f'"{t}"' for t in LC_TERMS + LC_MESH])
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmax": max_results, "sort": "pub+date"}

    r = requests.get(url, params=params)
    r.raise_for_status()

    pmids = [p.split("</Id>")[0] for p in r.text.split("<Id>")[1:]]
    return pmids

def fetch_pubmed_details(pmids):
    if not pmids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}

    r = requests.get(url, params=params)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "xml")
    papers = []

    for article in soup.find_all("PubmedArticle"):
        title = article.ArticleTitle.text.strip()
        abstract = article.Abstract.text.strip() if article.Abstract else ""
        pmid = article.PMID.text.strip()
        mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

        date_tag = article.find("PubDate")
        pub_date = datetime.today()
        if date_tag:
            y = date_tag.Year.text if date_tag.find("Year") else "2024"
            m = date_tag.Month.text if date_tag.find("Month") else "01"
            d = date_tag.Day.text if date_tag.find("Day") else "01"
            try:
                pub_date = datetime.strptime(f"{y}-{m}-{d}", "%Y-%m-%d")
            except:
                pass

        papers.append({
            "id": pmid,
            "title": title,
            "abstract": abstract,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source": "pubmed",
            "mesh": mesh_terms,
            "date": pub_date,
        })

    return papers

# ---------------------------------------------------------
# Nature
# ---------------------------------------------------------
def fetch_nature_results(max_results_per_term=50):
    results = []

    for term in LC_TERMS:
        url = f"{BASE_NATURE}/search?q={term.replace(' ', '+')}&order=date"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("article.c-card")[:max_results_per_term]:
            title_tag = a.select_one("h3 a")
            if not title_tag:
                continue

            title = title_tag.text.strip()
            link = BASE_NATURE + title_tag.get("href")
            snippet = a.select_one("p.c-card__summary")
            abstract = snippet.text.strip() if snippet else ""

            date_tag = a.select_one("time")
            pub_date = datetime.today()
            if date_tag and date_tag.has_attr("datetime"):
                try:
                    pub_date = datetime.fromisoformat(date_tag["datetime"])
                except:
                    pass

            results.append({
                "id": link,
                "title": title,
                "abstract": abstract,
                "url": link,
                "source": "nature",
                "mesh": [],
                "date": pub_date,
            })

    return list({r["id"]: r for r in results}.values())

# ---------------------------------------------------------
# HTML + GitHub Pages
# ---------------------------------------------------------
def format_html_card(p):
    return f"""
    <div class="paper-card">
        <h2>{p['title']}</h2>
        <p class="date">{p['date'].strftime('%Y-%m-%d')}</p>
        <p>{p['abstract']}</p>
        <p><a href="{p['url']}" target="_blank">Read more</a></p>
    </div>
    """

def append_to_github_pages(html):
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    updated = content.replace('<div id="papers">', f'<div id="papers">\n{html}\n')

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(updated)

    subprocess.run(["git", "-C", REPO_PATH, "add", "index.html"])
    subprocess.run(["git", "-C", REPO_PATH, "commit", "-m", "Update LC papers"])
    subprocess.run(["git", "-C", REPO_PATH, "push"])

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
def main():
    seen = load_seen()

    pmids = fetch_pubmed_pmids()
    pubmed = fetch_pubmed_details(pmids)
    nature = fetch_nature_results()

    filtered = [
        p for p in (pubmed + nature)
        if is_valid_lc_mechanism_paper(p)
    ]

    ranked = sorted(filtered, key=lambda p: (relevance_score(p), p["date"]), reverse=True)
    top = ranked[:10]

    new_count = 0

    for p in top:
        if p["id"] in seen:
            continue

        html = format_html_card(p)
        append_to_github_pages(html)

        seen.add(p["id"])
        new_count += 1

    save_seen(seen)
    print(f"[lc] Done. {new_count} new papers added to GitHub Pages.")

if __name__ == "__main__":
    main()
