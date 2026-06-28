import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import subprocess
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------
REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
INDEX_PATH = os.path.join(REPO_PATH, "index.html")
SEEN_FILE = os.path.join(REPO_PATH, "posted_pmids.txt")
LOG_PATH = os.path.join(REPO_PATH, "scheduler_log.txt")
BASE_NATURE = "https://www.nature.com"

# ---------------------------------------------------------
# FILTER TERMS
# ---------------------------------------------------------
LC_TERMS = [
    "long covid", "post covid", "post-covid", "post acute covid", "post-acute covid",
    "post covid condition", "post-covid condition", "post-acute sequelae", "pasc",
    "post-acute sars-cov-2",
]

LC_MESH = [
    "long covid", "post-acute covid-19 syndrome", "post-covid-19 condition",
    "post-acute sequelae of sars-cov-2 infection", "postviral fatigue syndrome",
]

MECHANISM_TERMS = [
    "mechanism", "pathophysiology", "pathogenesis", "immune", "immunological",
    "autoantibodies", "autoimmunity", "inflammation", "neuroinflammation",
    "endothelium", "endothelial", "microclots", "coagulation", "mitochondria",
    "mitochondrial", "metabolic", "metabolism", "viral persistence",
    "persistent virus", "reactivation", "herpesvirus", "ebv", "cmv",
    "autonomic", "dysautonomia", "pots", "neurological", "brain", "neuro",
]

TREATMENT_TERMS = [
    "treatment", "therapy", "therapeutic", "intervention", "clinical trial",
    "phase", "randomized", "randomised", "rehabilitation", "vagus nerve",
    "vagus nerve stimulation", "vns", "immunomodulation", "antiviral",
    "drug", "pharmacological", "exercise therapy", "pacing", "rehab",
    "protocol", "improvement", "recovery",
]

NOISE_TERMS = [
    "lung function", "exercise tolerance", "spirometer", "spirometry",
    "rehabilitation programme", "rehabilitation", "rehab", "balance",
    "survey", "cohort", "psychosocial", "healthcare utilization",
    "persistent symptoms", "chronic morbidity", "follow-up",
    "fitness", "dyspnea", "functional status", "workforce exit",
    "quality of life", "burden", "study protocol",
]

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
# SEEN
# ---------------------------------------------------------
def load_seen() -> set[str]:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())


def save_seen(seen: set[str]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in sorted(seen):
            f.write(item + "\n")

# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------
def is_strict_long_covid(p: dict) -> bool:
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()
    return any(kw in t or kw in a for kw in LC_TERMS)


def has_mesh_long_covid(p: dict) -> bool:
    return any(term.lower() in p.get("mesh", []) for term in LC_MESH)


def is_mechanism_or_treatment(p: dict) -> bool:
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()
    mech = any(kw in t or kw in a for kw in MECHANISM_TERMS)
    treat = any(kw in t or kw in a for kw in TREATMENT_TERMS)
    return mech or treat


def is_noise(p: dict) -> bool:
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()
    return any(kw in t or kw in a for kw in NOISE_TERMS)


def is_valid_lc_mech_paper(p: dict) -> bool:
    if not is_strict_long_covid(p):
        return False
    if p["source"] == "pubmed" and not has_mesh_long_covid(p):
        return False
    if not is_mechanism_or_treatment(p):
        return False
    if is_noise(p):
        return False
    return True


def relevance_score(p: dict) -> int:
    score = 0
    t = p["title"].lower()
    a = (p["abstract"] or "").lower()

    if is_strict_long_covid(p):
        score += 3
    if p["source"] == "pubmed" and has_mesh_long_covid(p):
        score += 3
    if any(kw in t or kw in a for kw in MECHANISM_TERMS):
        score += 2
    if any(kw in t or kw in a for kw in TREATMENT_TERMS):
        score += 2
    if len(a) > 400:
        score += 1
    if p["source"] == "nature":
        score += 1
    if p["source"] == "science":
        score += 1
    if is_noise(p):
        score -= 2

    return score

# ---------------------------------------------------------
# PUBMED API
# ---------------------------------------------------------
def fetch_pubmed_pmids(max_results: int = 200) -> list[str]:
    log("[lc] Searching PubMed…")

    query = " OR ".join([f'"{t}"' for t in LC_TERMS + LC_MESH])

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmax": max_results, "sort": "pub+date"}

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    pmids = [p.split("</Id>")[0] for p in r.text.split("<Id>")[1:]]
    log(f"[lc] Found PMIDs: {len(pmids)}")
    return pmids


def fetch_pubmed_details(pmids: list[str]) -> list[dict]:
    log("[lc] Fetching PubMed details…")
    if not pmids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "xml")
    papers: list[dict] = []

    for article in soup.find_all("PubmedArticle"):
        title = article.ArticleTitle.text if article.ArticleTitle else ""
        abstract = article.Abstract.text if article.Abstract else ""
        pmid = article.PMID.text if article.PMID else ""

        if not pmid or not title:
            continue

        mesh_terms = [m.text.lower() for m in article.find_all("DescriptorName")]

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
# NATURE 
# ---------------------------------------------------------
def fetch_nature_results(max_results: int = 50) -> list[dict]:
    log("[lc] Scraping Nature HTML…")

    results: list[dict] = []

    url = f"{BASE_NATURE}/search?q=long+covid&order=date"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    if r.status_code != 200:
        log(f"[lc] Nature search failed: {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    articles = (
        soup.select("article")
        or soup.select("[data-testid='search-result']")
        or soup.select("div.search-results__item")
    )

    for a in articles[:max_results]:
        title_tag = (
            a.select_one("h3 a")
            or a.select_one("h2 a")
            or a.select_one("a[href]")
        )
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if not href:
            continue

        link = href if href.startswith("http") else BASE_NATURE + href

        snippet_tag = a.select_one("p") or a.select_one("[data-testid='search-snippet']")
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        pub_date = datetime.today()
        date_tag = a.select_one("time")
        if date_tag:
            dt = date_tag.get("datetime") or date_tag.get_text(strip=True)
            if dt:
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        pub_date = datetime.strptime(dt[: len(fmt)], fmt)
                        break
                    except Exception:
                        continue

        results.append(
            {
                "id": link,
                "title": title,
                "abstract": snippet,
                "url": link,
                "source": "nature",
                "mesh": [],
                "date": pub_date,
            }
        )

    final = list({item["id"]: item for item in results}.values())
    log(f"[lc] Nature papers: {len(final)}")
    return final

# ---------------------------------------------------------
# SCIENCE (RSS fallback)
# ---------------------------------------------------------
def fetch_science_results(max_results: int = 50) -> list[dict]:
    log("[lc] Scraping Science RSS…")

    url = "https://www.science.org/action/rss?AllField=long+covid"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    if r.status_code != 200:
        log("[lc] Science RSS blocked.")
        return []

    soup = BeautifulSoup(r.text, "xml")
    items = soup.find_all("item")

    results: list[dict] = []

    for item in items[:max_results]:
        title = (item.title.text or "").strip()
        link = (item.link.text or "").strip()
        summary = (item.description.text or "").strip() if item.description else ""

        date_raw = (item.pubDate.text or "").strip() if item.pubDate else ""
        pub_date = datetime.today()
        for fmt in ("%a, %d %b %Y", "%Y-%m-%d"):
            try:
                pub_date = datetime.strptime(date_raw[: len(fmt)], fmt)
                break
            except Exception:
                continue

        results.append(
            {
                "id": link,
                "title": title,
                "abstract": summary,
                "url": link,
                "source": "science",
                "mesh": [],
                "date": pub_date,
            }
        )

    log(f"[lc] Science papers: {len(results)}")
    return results

# ---------------------------------------------------------
# HTML CARDS
# ---------------------------------------------------------
def build_card_html(p: dict) -> str:
    # Store full abstract in data-full so JS can calculate real read-time
    full_abstract = p['abstract'].replace('"', '&quot;').replace("'", "&#39;")

    return f"""
<div class="paper-card">
    <h2>{p['title']}</h2>
    <div class="date">{p['date'].strftime('%Y-%m-%d')}</div>

    <!-- Visible abstract (initially full, JS will collapse it) -->
    <p class="abstract" data-full="{full_abstract}">{p['abstract']}</p>

    <a href="{p['url']}" target="_blank">Read paper</a>

    <!-- Read-time placeholder -->
    <span class="read-time"></span>
</div>
""".strip()



def inject_cards_into_index(cards_html: str) -> None:
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    start = "<!-- SCRAPER_INJECT_START -->"
    end = "<!-- SCRAPER_INJECT_END -->"

    if start not in html or end not in html:
        raise RuntimeError("Injectiemarkers niet gevonden in index.html")

    before = html.split(start)[0]
    after = html.split(end)[1]

    new_html = before + start + "\n" + cards_html + "\n" + end + after

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

# ---------------------------------------------------------
# GIT
# ---------------------------------------------------------
def run_git(args: list[str]) -> None:
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_PATH,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        log(result.stdout.strip())
    if result.stderr:
        log(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(args)}")


def commit_and_push() -> None:
    run_git(["add", "."])
    run_git(["commit", "-m", "Update LC papers", "--allow-empty"])
    run_git(["push", "origin", "main"])

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main() -> None:
    os.chdir(REPO_PATH)
    log("Session: Console")

    seen = load_seen()

    pmids = fetch_pubmed_pmids()
    pubmed_papers = fetch_pubmed_details(pmids)
    nature_papers = fetch_nature_results()
    science_papers = fetch_science_results()

    all_raw = pubmed_papers + nature_papers + science_papers

    filtered = [p for p in all_raw if is_valid_lc_mech_paper(p)]

    ranked = sorted(filtered, key=lambda p: (relevance_score(p), p["date"]), reverse=True)
    top = ranked[:10]

    log(f"[lc] Selected papers: {len(top)}")

    new_papers = [p for p in top if p["id"] not in seen]

    if not new_papers:
        log("[lc] Geen nieuwe papers gevonden.")
        return

    cards_html = "\n\n".join(build_card_html(p) for p in new_papers)
    inject_cards_into_index(cards_html)

    for p in new_papers:
        seen.add(p["id"])
    save_seen(seen)

    commit_and_push()

    log(f"[lc] Done. {len(new_papers)} new papers added to GitHub Pages.")
    log("------------------------------")


if __name__ == "__main__":
    main()
