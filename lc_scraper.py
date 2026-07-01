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
REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
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
    # LC-term in titel/abstract
    if not is_strict_long_covid(p):
        return False

    # PubMed: mesh helpt, maar is niet meer verplicht
    if p["source"] == "pubmed":
        if not (has_mesh_long_covid(p) or is_mechanism_or_treatment(p)):
            return False

    # Mechanism of treatment verplicht
    if not is_mechanism_or_treatment(p):
        return False

    # Noise mag weg
    if is_noise(p):
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
# LitCovid (met correcte URL)
# ---------------------------------------------------------
LITCOVID_API = "https://www.ncbi.nlm.nih.gov/research/litcovid/api/records/"

def fetch_litcovid_results(max_results=200):
    print("[LitCovid] Fetching LitCovid papers...")
    params = {
        "query": "long covid OR post-acute sequelae OR PASC OR post covid",
        "page": 1,
        "pageSize": max_results,
    }
    try:
        r = requests.get(LITCOVID_API, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[LitCovid] ERROR fetching data: {e}")
        return []

    results = []
    for item in data.get("records", []):
        pmid = item.get("pmid") or item.get("uid")
        title = item.get("title") or ""
        abstract = item.get("abstract") or ""
        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else item.get("url", "")

        date_raw = item.get("publish_time") or ""
        pub_date = datetime.today()
        if date_raw:
            try:
                pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
            except:
                pass

        results.append({
            "id": pmid or f"litcovid-{title[:40]}",
            "title": title,
            "abstract": abstract,
            "url": link,
            "source": "litcovid",
            "mesh": [],
            "date": pub_date,
        })

    print(f"[LitCovid] Parsed papers: {len(results)}")
    return results

# ---------------------------------------------------------
# EuropePMC
# ---------------------------------------------------------
EUROPEPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

def fetch_europepmc_results(max_results=200):
    print("[EuropePMC] Fetching EuropePMC papers...")
    params = {
        "query": 'LONG COVID OR "post-acute sequelae" OR PASC OR "post covid"',
        "format": "json",
        "pageSize": max_results,
    }
    try:
        r = requests.get(EUROPEPMC_API, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[EuropePMC] ERROR fetching data: {e}")
        return []

    results = []
    for item in data.get("resultList", {}).get("result", []):
        title = item.get("title") or ""
        abstract = item.get("abstractText") or ""
        doi = item.get("doi")
        pmid = item.get("pmid")

        if pmid:
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            id_ = pmid
        elif doi:
            link = f"https://doi.org/{doi}"
            id_ = doi
        else:
            link = f"https://europepmc.org/article/{item.get('source','')}/{item.get('id','')}"
            id_ = f"europepmc-{item.get('id') or title[:40]}"

        date_raw = item.get("firstPublicationDate") or item.get("pubYear") or ""
        pub_date = datetime.today()
        if date_raw:
            try:
                if len(date_raw) == 4:
                    pub_date = datetime.strptime(date_raw, "%Y")
                else:
                    pub_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
            except:
                pass

        results.append({
            "id": id_,
            "title": title,
            "abstract": abstract,
            "url": link,
            "source": "europepmc",
            "mesh": [],
            "date": pub_date,
        })

    print(f"[EuropePMC] Parsed papers: {len(results)}")
    return results

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
    litcovid = fetch_litcovid_results()
    europepmc = fetch_europepmc_results()

    all_papers = pubmed + nature + litcovid + europepmc

    filtered = [
        p for p in all_papers
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
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import subprocess
from datetime import datetime

# Absolute path to your repo
REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
INDEX_PATH = os.path.join(REPO_PATH, "index.html")
LOG_PATH = os.path.join(REPO_PATH, "scheduler_log.txt")

# Storage modules
from storage.seen import load_seen, save_seen
from storage.cache import load_ai_cache, save_ai_cache

# Source modules (expanded)
from sources.pubmed import fetch_pubmed_papers
from sources.nature import fetch_nature_papers
from sources.europepmc import fetch_europepmc_papers
from sources.litcovid import fetch_litcovid_papers
from sources.longcovidweb import fetch_longcovidweb_papers
from sources.recover import fetch_recover_papers
from sources.rki import fetch_rki_papers
from sources.scienceopen import fetch_scienceopen_papers

# AI classifier
from ai.classifier import classify_paper

# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ---------------------------------------------------------
# PREFILTER (SAFE)
# ---------------------------------------------------------

LC_TERMS = ["long covid", "post covid", "post-covid", "pasc", "post-acute", "sars-cov-2"]
MECH_TERMS = ["immune", "inflammation", "mitochondria", "viral", "persistent", "neurological"]
TREAT_TERMS = ["treatment", "therapy", "drug", "trial", "intervention"]
NOISE_TERMS = ["survey", "protocol", "quality of life", "burden"]

def is_valid_candidate(p: dict) -> bool:
    title = p.get("title") or ""
    abstract = p.get("abstract") or ""

    if not isinstance(title, str):
        title = str(title)
    if not isinstance(abstract, str):
        abstract = str(abstract)

    t = title.lower()
    a = abstract.lower()

    # LC relevance
    if not any(kw in t or kw in a for kw in LC_TERMS):
        if "covid" not in t:
            return False

    # Mechanism or treatment
    mech = any(kw in t or kw in a for kw in MECH_TERMS)
    treat = any(kw in t or kw in a for kw in TREAT_TERMS)
    if not (mech or treat):
        return False

    # Noise filter
    if any(kw in t or kw in a for kw in NOISE_TERMS):
        return False

    return True

# ---------------------------------------------------------
# HTML CARD GENERATION
# ---------------------------------------------------------

def build_card_html(p: dict) -> str:
    full_abstract = (p["abstract"] or "").replace('"', '&quot;').replace("'", "&#39;")
    ai_summary = (p.get("ai_summary", "") or "").replace('"', '&quot;').replace("'", "&#39;")

    date_obj = p.get("date")
    if isinstance(date_obj, datetime):
        date_str = date_obj.strftime("%Y-%m-%d")
    else:
        date_str = str(date_obj)

    return f"""
<div class="paper-card">
    <h2>{p['title']}</h2>
    <div class="date">{date_str}</div>

    <div class="ai-meta">
        <span class="ai-category">Category: {p.get('ai_category', '')}</span>
        <span class="ai-score">AI relevance: {p.get('ai_score', 0)}/100</span>
    </div>

    <p class="ai-summary">{ai_summary}</p>

    <button class="toggle-abstract" onclick="this.nextElementSibling.classList.toggle('hidden'); this.textContent = this.nextElementSibling.classList.contains('hidden') ? 'Show abstract' : 'Hide abstract';">
        Show abstract
    </button>

    <p class="abstract hidden" data-full="{full_abstract}">{p['abstract']}</p>

    <a href="{p['url']}" target="_blank">Read paper</a>
</div>
""".strip()

def inject_cards_into_index(cards_html: str) -> None:
    print("[HTML] Injecting cards into index.html...")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    start = "<!-- SCRAPER_INJECT_START -->"
    end = "<!-- SCRAPER_INJECT_END -->"

    before = html.split(start)[0]
    after = html.split(end)[1]

    new_html = before + start + "\n" + cards_html + "\n" + end + after

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

# ---------------------------------------------------------
# GIT
# ---------------------------------------------------------

def run_git(args: list[str]) -> None:
    print(f"[GIT] Running git command: {' '.join(args)}")
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_PATH,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print("[GIT STDOUT]", result.stdout.strip())
    if result.stderr:
        print("[GIT STDERR]", result.stderr.strip())

def commit_and_push() -> None:
    run_git(["add", "."])
    run_git(["commit", "-m", "Update LC papers", "--allow-empty"])
    run_git(["push", "origin", "main"])

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main() -> None:
    print("\n================ LC SCRAPER START ================\n")

    seen = load_seen()
    ai_cache = load_ai_cache()

    print("[FETCH] Fetching PubMed papers...")
    pubmed = fetch_pubmed_papers()
    print(f"[FETCH] PubMed: {len(pubmed)} papers")

    print("[FETCH] Fetching Nature papers...")
    nature = fetch_nature_papers()
    print(f"[FETCH] Nature: {len(nature)} papers")

    print("[FETCH] Fetching Europe PMC papers...")
    europepmc = fetch_europepmc_papers()
    print(f"[FETCH] Europe PMC: {len(europepmc)} papers")

    print("[FETCH] Fetching LitCovid papers...")
    litcovid = fetch_litcovid_papers()
    print(f"[FETCH] LitCovid: {len(litcovid)} papers")

    print("[FETCH] Fetching LongCovidWeb papers...")
    longcovidweb = fetch_longcovidweb_papers()
    print(f"[FETCH] LongCovidWeb: {len(longcovidweb)} papers")

    print("[FETCH] Fetching RECOVER papers...")
    recover = fetch_recover_papers()
    print(f"[FETCH] RECOVER: {len(recover)} papers")

    print("[FETCH] Fetching RKI papers...")
    rki = fetch_rki_papers()
    print(f"[FETCH] RKI: {len(rki)} papers")

    print("[FETCH] Fetching ScienceOpen papers...")
    scienceopen = fetch_scienceopen_papers()
    print(f"[FETCH] ScienceOpen: {len(scienceopen)} papers")

    # Merge all sources
    all_raw = (
        pubmed +
        nature +
        europepmc +
        litcovid +
        longcovidweb +
        recover +
        rki +
        scienceopen
    )

    print(f"[MERGE] Total fetched: {len(all_raw)} papers")

    print("[PREFILTER] Running prefilter...")
    candidates = []
    for p in all_raw:
        try:
            if is_valid_candidate(p):
                candidates.append(p)
        except Exception as e:
            print(f"[PREFILTER ERROR] Paper {p.get('id')} crashed: {e}")

    print(f"[PREFILTER] Candidates: {len(candidates)}")

    print("[AI] Starting AI classification...")
    enriched = []
    total = len(candidates)

    for idx, p in enumerate(candidates, start=1):
        print(f"[AI] ({idx}/{total}) Classifying: {p.get('title','')[:80]}")

        ai = classify_paper(p, ai_cache)

        print(f"[AI] Result → score={ai['score']} category={ai['category']} long_covid={ai['long_covid']}")

        if not ai.get("long_covid"):
            print("[AI] Skipped (not LC)")
            continue
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            print("[AI] Skipped (category irrelevant)")
            continue
        if ai.get("score", 0) < 70:
            print("[AI] Skipped (score < 70)")
            continue

        p["ai_score"] = ai["score"]
        p["ai_category"] = ai["category"]
        p["ai_summary"] = ai["summary"]
        p["ai_reason"] = ai["reason"]

        enriched.append(p)

    save_ai_cache(ai_cache)
    print(f"[AI] Selected after filtering: {len(enriched)}")

    if not enriched:
        print("[DONE] No enriched papers.")
        return

    print("[RANK] Ranking papers...")
    ranked = sorted(
        enriched,
        key=lambda p: (p.get("ai_score", 0), p.get("date", datetime.min)),
        reverse=True,
    )

    top = ranked[:10]
    print(f"[RANK] Top papers: {len(top)}")

    new_papers = [p for p in top if p.get("id") not in seen]
    print(f"[NEW] New papers: {len(new_papers)}")

    if not new_papers:
        print("[DONE] No new papers to inject.")
        commit_and_push()
        return

    print("[HTML] Building HTML cards...")
    cards_html = "\n\n".join(build_card_html(p) for p in new_papers)

    inject_cards_into_index(cards_html)

    print("[SEEN] Updating seen list...")
    for p in new_papers:
        seen.add(p["id"])
    save_seen(seen)

    print("[GIT] Committing and pushing...")
    commit_and_push()

    print(f"[DONE] Added {len(new_papers)} new papers.")
    print("\n================ LC SCRAPER END ================\n")

if __name__ == "__main__":
    main()
