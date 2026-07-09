import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import subprocess
from datetime import datetime
import concurrent.futures

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
from sources.europepmc import fetch_europepmc_papers
from sources.longcovidweb import fetch_longcovidweb_papers
from sources.recover import fetch_recover_papers
from sources.rki import fetch_rki_papers
from sources.litcovid import fetch_litcovid_html_long_covid
from sources.patientresearchcovid19 import fetch_plrc_papers

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
        pass


# ---------------------------------------------------------
# PREFILTER
# ---------------------------------------------------------

LC_TERMS = [
    "long covid", "post covid", "post-covid", "pasc",
    "post-acute", "post-acute sequelae", "sequelae",
    "post-viral", "post-infectious", "post-infection",
    "post-sars-cov-2", "chronic covid", "long-term covid",
    "sars-cov-2", "covid-19", "covid 19"
]

MECH_TERMS = [
    "immune", "immunity", "inflammation", "cytokine", "interferon",
    "autoimmune", "autoimmunity", "autoantibody",
    "t-cell", "b-cell", "innate", "adaptive",
    "viral", "virus", "persistent", "persistence", "reservoir",
    "reactivation", "latency",
    "neurological", "neuro", "neuroinflammation", "neuroimmune",
    "microglia", "glial",
    "endothelial", "endothelium", "microclots", "microvascular",
    "coagulation", "thrombosis", "vascular",
    "mitochondria", "mitochondrial", "oxidative stress",
    "metabolic", "metabolism"
]

TREAT_TERMS = [
    "treatment", "therapy", "drug", "intervention", "rehabilitation",
    "trial", "clinical trial", "clinical study",
    "randomized", "controlled", "rct",
    "phase", "phase 1", "phase 2", "phase 3", "phase 4",
    "phase iib", "dose-ranging",
    "pilot", "pilot trial", "open-label", "double-blind",
    "single-blind", "double-masked", "multi-center",
    "placebo", "placebo-controlled", "sham-controlled",
    "prospective", "retrospective", "observational study",
    "efficacy", "evaluation", "feasibility",
    "naltrexone", "ldn", "low-dose naltrexone"
]

NOISE_TERMS = [
    "survey", "protocol", "quality of life", "burden",
    "opinion", "editorial", "review", "meta-analysis",
    "scoping review", "narrative review"
]

def _contains_any(text: str, terms: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in terms)


def is_valid_candidate_pubmed_nature(p: dict) -> bool:
    combo = ((p.get("title") or "") + " " + (p.get("abstract") or "")).lower()

    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    if not (_contains_any(combo, MECH_TERMS) or _contains_any(combo, TREAT_TERMS)):
        return False

    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


def is_valid_candidate_europepmc(p: dict) -> bool:
    combo = ((p.get("title") or "") + " " + (p.get("abstract") or "")).lower()

    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


def is_valid_candidate_generic(p: dict) -> bool:
    combo = ((p.get("title") or "") + " " + (p.get("abstract") or "")).lower()

    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


def is_valid_candidate(p: dict) -> bool:
    if not isinstance(p.get("date"), datetime):
        return False

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

def build_card_html(p: dict) -> str:
    # Skip papers with missing critical fields
    if not p.get("title") or not p.get("url"):
        return ""

    abstract = p.get("abstract") or p.get("ai_summary") or "No abstract available."


    source = (p.get("source", "other") or "other").lower()

    def _source_display_name(s: str) -> str:
        mapping = {
            "pubmed": "PubMed",
            "nature": "Nature",
            "europepmc": "EuropePMC",
            "litcovid": "LitCovid",
            "longcovidweb": "LongCovidWeb",
            "recover": "RECOVER",
            "rki": "RKI",
            "patientresearchcovid19": "PatientResearch",
        }
        return mapping.get(s.lower(), "Other")

    source_name = _source_display_name(source)

    category_raw = p.get("ai_category", "") or ""
    category = category_raw.lower()
    group = (p.get("ai_mechanistic_group") or "").lower()

    full_abstract = (p.get("abstract", "") or "").replace('"', '&quot;').replace("'", "&#39;")
    ai_summary = (p.get("ai_summary", "") or "").replace('"', '&quot;').replace("'", "&#39;")

    date_obj = p.get("date")
    date_str = date_obj.strftime("%Y-%m-%d") if isinstance(date_obj, datetime) else ""

    return f"""
<div class="paper-card" data-source="{source}" data-category="{category}" data-mech="{group}">
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
        onclick="
            const abs = this.parentElement.querySelector('.abstract');
            abs.classList.toggle('hidden');
            this.textContent = abs.classList.contains('hidden')
                ? 'Show abstract'
                : 'Hide abstract';
        ">
        Show abstract
    </button>

    <p class="abstract hidden" data-full="{full_abstract}">{p.get('abstract','')}</p>

    <a href="{p.get('url','')}" target="_blank">Read paper</a>
</div>
""".strip()




# ---------------------------------------------------------
# STATISTICS (mechanistic groups)
# ---------------------------------------------------------

def compute_stats(papers):
    stats = {"total": len(papers)}
    for p in papers:
        group = (p.get("ai_mechanistic_group") or "").lower()
        if group not in stats:
            stats[group] = 0
        stats[group] += 1
    return stats

    
def build_compact_header(stats):
    icons = {
        "autoimmunity": "🧬",
        "neuroinflammation": "🧠",
        "immune dysregulation": "⚠️",
        "dysautonomia": "⚡",
        "viral persistence": "🔥",
        "microvascular": "💉",
        "mitochondrial": "🔋",
        "non-mechanistic": "📄",
    }

    parts = []

    for group, count in stats.items():
        if group == "total":
            continue

        icon = icons.get(group, "🔎")
        label = group.replace("-", " ").title()

        parts.append(f"{icon} {label}: {count}")

    return " &nbsp;•&nbsp; ".join(parts)


def inject_stats_into_index(stats):
    log("[HTML] Injecting statistics into index.html...")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    header_html = build_compact_header(stats)

    html = re.sub(
        r'<div id="mechanism-stats">.*?</div>',
        f'<div id="mechanism-stats">{header_html}</div>',
        html,
        flags=re.DOTALL
    )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)

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
# HTML injection for cards
# ---------------------------------------------------------

def inject_cards_into_index(cards_html: str) -> None:
    log("[HTML] Injecting cards into index.html...")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    start = "<!-- SCRAPER_INJECT_START -->"
    end = "<!-- SCRAPER_INJECT_END -->"

    if start not in html or end not in html:
        raise RuntimeError("Inject markers not found in index.html")

    # Split in één keer
    before, middle_and_after = html.split(start, 1)
    _, after = middle_and_after.split(end, 1)

    new_html = before + start + "\n" + cards_html + "\n" + end + after

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

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
        "litcovid": fetch_litcovid_html_long_covid(),
        "longcovidweb": fetch_longcovidweb_papers(),
        "recover": fetch_recover_papers(),
        "rki": fetch_rki_papers(),
        "patientresearchcovid19": fetch_plrc_papers(),
    }

    for name, papers in sources.items():
        log(f"[FETCH] {name}: {len(papers)} papers")

    all_raw = []
    for papers in sources.values():
        all_raw.extend(papers)

    log(f"[MERGE] Total fetched: {len(all_raw)} papers")

    # TEST MODE — limit number of papers
    all_raw = all_raw[:20]
    log(f"[TEST] Limiting to {len(all_raw)} papers for fast testing")

    candidates = [p for p in all_raw if is_valid_candidate(p)]
    log(f"[PREFILTER] Candidates: {len(candidates)}")

    if not candidates:
        log("[AI] No candidates after prefilter.")
        print("\n================ LC SCRAPER END ================\n")
        return

    # ---------------------------------------------------------
    # PARALLEL AI CLASSIFICATION
    # ---------------------------------------------------------

    log(f"[AI] Running parallel classification on {len(candidates)} papers...")

    results = {}
    completed = 0
    total = len(candidates)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {
            executor.submit(classify_paper, p, ai_cache): p
            for p in candidates
        }

        for future in concurrent.futures.as_completed(future_map):
            p = future_map[future]
            ai = future.result()
            results[p["id"]] = ai

            completed += 1
            title_preview = p.get("title", "")[:80]
            log(f"[AI] ({completed}/{total}) Done: {title_preview}")

    # ---------------------------------------------------------
    # FILTERING
    # ---------------------------------------------------------

    enriched = []
    for p in candidates:
        ai = results.get(p.get("id"))

        # Skip AI failures (None)
        if not isinstance(ai, dict):
            continue

        # Skip irrelevant categories
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue

        # Skip low scores
        if ai.get("score", 0) < 60:
            continue

        # Attach AI metadata
        p["ai_score"] = ai.get("score", 0)
        p["ai_category"] = ai.get("category", "Irrelevant")
        p["ai_mechanistic_group"] = ai.get("mechanistic_group", "Non-mechanistic")
        p["ai_summary"] = ai.get("summary", p.get("abstract", "")[:400])
        p["ai_reason"] = ai.get("reason", "")

        enriched.append(p)

    save_ai_cache(ai_cache)
    log(f"[AI] Selected after filtering: {len(enriched)}")

    if not enriched:
        log("[DONE] No enriched papers.")
        commit_and_push()
        print("\n================ LC SCRAPER END ================\n")
        return

    ranked = sorted(
        enriched,
        key=lambda p: (p.get("ai_score", 0), p.get("date", datetime.min)),
        reverse=True,
    )

    top = [p for p in ranked if p["ai_score"] >= 70]
    log(f"[RANK] Top papers: {len(top)}")

    # STATS
    stats = compute_stats(top)
    inject_stats_into_index(stats)
    log("[STATS] " + ", ".join(f"{k.upper()}={v}" for k, v in stats.items()))

    new_papers = [p for p in top if p.get("id") not in seen]
    log(f"[NEW] New papers: {len(new_papers)}")

    if not new_papers:
        log("[DONE] No new papers to inject.")
        commit_and_push()
        print("\n================ LC SCRAPER END ================\n")
        return

    cards_html = "\n\n".join(build_card_html(p) for p in new_papers)
    inject_cards_into_index(cards_html)

    # SECOND PASS: POST RELEVANT PAPERS FROM ai_cache.json
    log("[CACHE] Checking cached papers for missed relevant items...")

    cached_new = []

    for paper_id, ai in ai_cache.items():
        if paper_id in seen:
            continue
        if not ai.get("long_covid"):
            continue
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue
        if ai.get("score", 0) < 60:
            continue

        original = next((p for p in all_raw if p.get("id") == paper_id), None)
        if not original:
            continue

        if not isinstance(original.get("date"), datetime):
            continue

        original["ai_score"] = ai["score"]
        original["ai_category"] = ai["category"]
        original["ai_mechanistic_group"] = ai.get("mechanistic_group", "Non-mechanistic")
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
