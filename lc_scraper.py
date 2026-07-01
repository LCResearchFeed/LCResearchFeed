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

# Uniform source modules
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
# PREFILTER
# ---------------------------------------------------------

LC_TERMS = ["long covid", "post covid", "post-covid", "pasc", "post-acute", "sars-cov-2"]
MECH_TERMS = ["immune", "inflammation", "mitochondria", "viral", "persistent", "neurological"]
TREAT_TERMS = ["treatment", "therapy", "drug", "trial", "intervention"]
NOISE_TERMS = ["survey", "protocol", "quality of life", "burden"]

def is_valid_candidate(p: dict) -> bool:
    title = (p.get("title") or "")
    abstract = (p.get("abstract") or "")

    if not isinstance(title, str):
        title = str(title)
    if not isinstance(abstract, str):
        abstract = str(abstract)

    title = title.lower()
    abstract = abstract.lower()

    if not any(kw in title or kw in abstract for kw in LC_TERMS):
        if "covid" not in title:
            return False

    mech = any(kw in title or kw in abstract for kw in MECH_TERMS)
    treat = any(kw in title or kw in abstract for kw in TREAT_TERMS)
    if not (mech or treat):
        return False

    if any(kw in title or kw in abstract for kw in NOISE_TERMS):
        return False

    return True

# ---------------------------------------------------------
# HTML CARD GENERATION
# ---------------------------------------------------------

def build_card_html(p: dict) -> str:
    full_abstract = (p.get("abstract", "") or "").replace('"', '&quot;').replace("'", "&#39;")
    ai_summary = (p.get("ai_summary", "") or "").replace('"', '&quot;').replace("'", "&#39;")

    date_obj = p.get("date")
    if isinstance(date_obj, datetime):
        date_str = date_obj.strftime("%Y-%m-%d")
    else:
        date_str = str(date_obj)

    return f"""
<div class="paper-card" data-source="{p.get('source','other')}">
    <h2>{p.get('title','')}</h2>
    <div class="date">{date_str}</div>

    <div class="ai-meta">
        <span class="ai-category">Category: {p.get('ai_category', '')}</span>
        <span class="ai-score">AI relevance: {p.get('ai_score', 0)}/100</span>
    </div>

    <p class="ai-summary">{ai_summary}</p>

    <button class="toggle-abstract"
        onclick="this.nextElementSibling.classList.toggle('hidden');
                 this.textContent = this.nextElementSibling.classList.contains('hidden')
                 ? 'Show abstract' : 'Hide abstract';">
        Show abstract
    </button>

    <p class="abstract hidden" data-full="{full_abstract}">{p.get('abstract','')}</p>

    <a href="{p.get('url','')}" target="_blank">Read paper</a>
</div>
""".strip()

def inject_cards_into_index(cards_html: str) -> None:
    log("[HTML] Injecting cards into index.html...")
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
    log(f"[GIT] Running git command: {' '.join(args)}")
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

    # FETCH ALL SOURCES
    sources = {
        "pubmed": fetch_pubmed_papers(),
        "nature": fetch_nature_papers(),
        "europepmc": fetch_europepmc_papers(),
        "litcovid": fetch_litcovid_papers(),
        "longcovidweb": fetch_longcovidweb_papers(),
        "recover": fetch_recover_papers(),
        "rki": fetch_rki_papers(),
        "scienceopen": fetch_scienceopen_papers(),
    }

    # ENSURE EACH PAPER HAS A SOURCE LABEL
    for name, papers in sources.items():
        for p in papers:
            # alleen zetten als het nog niet bestaat
            p.setdefault("source", name)

    for name, papers in sources.items():
        log(f"[FETCH] {name}: {len(papers)} papers")

    # MERGE
    all_raw = []
    for papers in sources.values():
        all_raw.extend(papers)

    log(f"[MERGE] Total fetched: {len(all_raw)} papers")

    # PREFILTER
    candidates = []
    for p in all_raw:
        try:
            if is_valid_candidate(p):
                candidates.append(p)
        except Exception as e:
            print(f"[PREFILTER ERROR] Paper {p.get('id')} crashed: {e}")

    log(f"[PREFILTER] Candidates: {len(candidates)}")

    # AI CLASSIFICATION
    enriched = []
    total = len(candidates)

    for idx, p in enumerate(candidates, start=1):
        log(f"[AI] ({idx}/{total}) Classifying: {p.get('title','')[:80]}")
        ai = classify_paper(p, ai_cache)

        if not ai.get("long_covid"):
            continue
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue
        if ai.get("score", 0) < 70:
            continue

        p["ai_score"] = ai["score"]
        p["ai_category"] = ai["category"]
        p["ai_summary"] = ai["summary"]
        p["ai_reason"] = ai["reason"]

        enriched.append(p)

    save_ai_cache(ai_cache)
    log(f"[AI] Selected after filtering: {len(enriched)}")

    if not enriched:
        log("[DONE] No enriched papers.")
        return

    # RANK
    ranked = sorted(
        enriched,
        key=lambda p: (p.get("ai_score", 0), p.get("date", datetime.min)),
        reverse=True,
    )

    top = ranked[:10]
    log(f"[RANK] Top papers: {len(top)}")

    # NEW
    new_papers = [p for p in top if p.get("id") not in seen]
    log(f"[NEW] New papers: {len(new_papers)}")

    if not new_papers:
        log("[DONE] No new papers to inject.")
        commit_and_push()
        return

    # HTML
    cards_html = "\n\n".join(build_card_html(p) for p in new_papers)
    inject_cards_into_index(cards_html)

    # SEEN
    for p in new_papers:
        seen.add(p["id"])
    save_seen(seen)

    # GIT
    commit_and_push()

    log(f"[DONE] Added {len(new_papers)} new papers.")
    print("\n================ LC SCRAPER END ================\n")

if __name__ == "__main__":
    main()
