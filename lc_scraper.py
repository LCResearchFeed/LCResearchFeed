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

# Source modules
from sources.pubmed import fetch_pubmed_papers
from sources.nature import fetch_nature_papers
from sources.science import fetch_science_papers

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
    full_abstract = (p["abstract"] or "").replace('"', '&quot;')
    ai_summary = (p.get("ai_summary", "") or "").replace('"', '&quot;')

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
    <p class="abstract" data-full="{full_abstract}">{p['abstract']}</p>

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

    print("[FETCH] Fetching Science papers...")
    science = fetch_science_papers()
    print(f"[FETCH] Science: {len(science)} papers")

    all_raw = pubmed + nature + science
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
