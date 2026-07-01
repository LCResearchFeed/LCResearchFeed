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
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # logging mag nooit het script breken
        pass

# ---------------------------------------------------------
# PREFILTER
# ---------------------------------------------------------

LC_TERMS = ["long covid", "post covid", "post-covid", "pasc", "post-acute", "sars-cov-2", "covid-19", "covid 19"]
MECH_TERMS = ["immune", "immunity", "inflammation", "mitochondria", "mitochondrial",
              "viral", "virus", "persistent", "reservoir", "neurological", "neuro"]
TREAT_TERMS = ["treatment", "therapy", "drug", "trial", "intervention", "rehabilitation"]
NOISE_TERMS = ["survey", "protocol", "quality of life", "burden", "opinion", "editorial"]


def _contains_any(text: str, terms: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in terms)


def is_valid_candidate_pubmed_nature(p: dict) -> bool:
    title = (p.get("title") or "").lower()
    abstract = (p.get("abstract") or "").lower()
    combo = title + " " + abstract

    if not _contains_any(combo, LC_TERMS):
        if "covid" not in combo:
            return False

    mech = _contains_any(combo, MECH_TERMS)
    treat = _contains_any(combo, TREAT_TERMS)
    if not (mech or treat):
        return False

    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


def is_valid_candidate_europepmc(p: dict) -> bool:
    title = (p.get("title") or "").lower()
    abstract = (p.get("abstract") or "").lower()
    combo = title + " " + abstract

    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


def is_valid_candidate_generic(p: dict) -> bool:
    title = (p.get("title") or "").lower()
    abstract = (p.get("abstract") or "").lower()
    combo = title + " " + abstract

    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


def is_valid_candidate(p: dict) -> bool:
    source = (p.get("source") or "").lower()

    if source in ("pubmed", "nature"):
        return is_valid_candidate_pubmed_nature(p)
    elif source == "europepmc":
        return is_valid_candidate_europepmc(p)
    else:
        return is_valid_candidate_generic(p)

# ---------------------------------------------------------
# HTML CARD GENERATION
# ---------------------------------------------------------

def _source_display_name(source: str) -> str:
    s = (source or "").lower()
    if s == "pubmed":
        return "PubMed"
    if s == "nature":
        return "Nature"
    if s == "europepmc":
        return "EuropePMC"
    if s == "litcovid":
        return "LitCovid"
    if s == "longcovidweb":
        return "LongCovidWeb"
    if s == "recover":
        return "RECOVER"
    if s == "rki":
        return "RKI"
    if s == "scienceopen":
        return "ScienceOpen"
    return "Other"


def build_card_html(p: dict) -> str:
    # Bron
    source = (p.get("source", "other") or "other").lower()

    # Bron-naam voor badge
    def _source_display_name(s: str) -> str:
        mapping = {
            "pubmed": "PubMed",
            "nature": "Nature",
            "europepmc": "EuropePMC",
            "litcovid": "LitCovid",
            "scienceopen": "ScienceOpen",
            "longcovidweb": "LongCovidWeb",
            "recover": "RECOVER",
            "rki": "RKI",
        }
        return mapping.get(s.lower(), "Other")

    source_name = _source_display_name(source)

    # Onderwerp / categorie
    category_raw = p.get("ai_category", "") or ""
    category = category_raw.lower()

    # Abstract + summary escaping
    full_abstract = (p.get("abstract", "") or "").replace('"', '&quot;').replace("'", "&#39;")
    ai_summary = (p.get("ai_summary", "") or "").replace('"', '&quot;').replace("'", "&#39;")

    # Datum
    date_obj = p.get("date")
    if isinstance(date_obj, datetime):
        date_str = date_obj.strftime("%Y-%m-%d")
    else:
        date_str = str(date_obj) if date_obj else ""

    return f"""
<div class="paper-card" data-source="{source}" data-category="{category}">
    <span class="source-badge source-{source}">{source_name}</span>
    <span class="subject-badge">{category_raw}</span>

    <h2>{p.get('title','')}</h2>
    <div class="date">{date_str}</div>

    <div class="ai-meta">
        <span class="ai-category">Category: {category_raw}</span>
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

    if start not in html or end not in html:
        raise RuntimeError("Inject markers not found in index.html")

    before, _ = html.split(start, 1)
    _, after = html.split(end, 1)

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

    for name, papers in sources.items():
        log(f"[FETCH] {name}: {len(papers)} papers")

    all_raw: list[dict] = []
    for papers in sources.values():
        all_raw.extend(papers)

    log(f"[MERGE] Total fetched: {len(all_raw)} papers")

    candidates = [p for p in all_raw if is_valid_candidate(p)]
    log(f"[PREFILTER] Candidates: {len(candidates)}")

    enriched: list[dict] = []
    total = len(candidates)

    for idx, p in enumerate(candidates, start=1):
        title_preview = p.get("title", "")[:80]
        log(f"[AI] ({idx}/{total}) Classifying: {title_preview}")
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

    ranked = sorted(
        enriched,
        key=lambda p: (p.get("ai_score", 0), p.get("date", datetime.min)),
        reverse=True,
    )

    top = [p for p in ranked if p["ai_score"] >= 70]
    log(f"[RANK] Top papers: {len(top)}")

    new_papers = [p for p in top if p.get("id") not in seen]
    log(f"[NEW] New papers: {len(new_papers)}")

    if not new_papers:
        log("[DONE] No new papers to inject.")
        commit_and_push()
        return

    cards_html = "\n\n".join(build_card_html(p) for p in new_papers)
    inject_cards_into_index(cards_html)
    
    # ---------------------------------------------------------
    # SECOND PASS: POST RELEVANT PAPERS FROM ai_cache.json
    # ---------------------------------------------------------

    log("[CACHE] Checking cached papers for missed relevant items...")

    cached_new = []

    for paper_id, ai in ai_cache.items():
        # Skip if already posted
        if paper_id in seen:
            continue

        # Skip if AI says not long covid
        if not ai.get("long_covid"):
            continue

        # Skip irrelevant categories
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue

        # Skip low score
        if ai.get("score", 0) < 70:
            continue

        # We need the original paper data from all_raw
        original = next((p for p in all_raw if p.get("id") == paper_id), None)
        if not original:
            continue

        # Attach AI fields
        original["ai_score"] = ai["score"]
        original["ai_category"] = ai["category"]
        original["ai_summary"] = ai["summary"]
        original["ai_reason"] = ai["reason"]

        cached_new.append(original)

    log(f"[CACHE] Missed relevant papers found: {len(cached_new)}")

    if cached_new:
        cached_html = "\n\n".join(build_card_html(p) for p in cached_new)
        inject_cards_into_index(cached_html)

    for p in cached_new:
        seen.add(p["id"])
    save_seen(seen)

    log(f"[CACHE] Added {len(cached_new)} cached relevant papers.")


    for p in new_papers:
        if "id" in p:
            seen.add(p["id"])
    save_seen(seen)

    commit_and_push()

    log(f"[DONE] Added {len(new_papers)} new papers.")
    print("\n================ LC SCRAPER END ================\n")


if __name__ == "__main__":
    main()
