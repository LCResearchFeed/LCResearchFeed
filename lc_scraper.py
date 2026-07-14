import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import subprocess
from datetime import datetime
import concurrent.futures

# Absolute path to repo
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

# LOGGING

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# PREFILTER

LC_TERMS = [
    "long covid",
    "long-covid",
    "long COVID syndrome",
    "long COVID condition",
    "post covid",
    "post-covid",
    "post-COVID condition",
    "post COVID condition",
    "post-COVID-19 condition",
    "PCC",
    "PASC",
    "post-acute sequelae",
    "post-acute sequelae of SARS-CoV-2 infection",
    "post-acute COVID-19 syndrome",
    "post-acute COVID syndrome",
    "post acute COVID",
    "post-viral syndrome",
    "post viral syndrome",
    "post-infectious syndrome",
    "post infectious syndrome",
    "post-acute infection syndrome",
    "PAIS",
    "chronic COVID",
    "chronic COVID-19",
    "persistent COVID",
    "persistent COVID-19",
    "ongoing symptomatic COVID-19",
    "long-term COVID",
    "post-SARS-CoV-2",
    "post SARS-CoV-2",
    "LTC",
    "LC",
]

MECH_TERMS = [
    "immune",
    "immunity",
    "immune dysregulation",
    "immune dysfunction",
    "inflammation",
    "inflammatory",
    "cytokine",
    "cytokine storm",
    "interferon",
    "autoimmune",
    "autoimmunity",
    "autoantibody",
    "autoantibodies",
    "antibody",
    "complement",
    "mast cell",
    "mast cell activation",
    "MCAS",
    "t-cell",
    "T cell",
    "b-cell",
    "B cell",
    "innate",
    "adaptive",
    "NK cell",
    "natural killer",
    "viral",
    "virus",
    "viral persistence",
    "persistent infection",
    "persistence",
    "reservoir",
    "viral reservoir",
    "reactivation",
    "latency",
    "latent",
    "neurological",
    "neurologic",
    "neuro",
    "neuroinflammation",
    "neuroimmune",
    "microglia",
    "glial",
    "blood brain barrier",
    "BBB",
    "brain fog",
    "cognitive dysfunction",
    "endothelial",
    "endothelium",
    "endothelial dysfunction",
    "microclots",
    "microvascular",
    "vascular",
    "coagulation",
    "thrombosis",
    "platelet",
    "platelet activation",
    "fibrin",
    "fibrinogen",
    "mitochondria",
    "mitochondrial",
    "oxidative stress",
    "metabolic",
    "metabolism",
    "energy metabolism",
    "cellular energy",
    "ATP",
    "autonomic",
    "autonomic dysfunction",
    "dysautonomia",
    "orthostatic intolerance",
    "POTS",
    "postural tachycardia",
    "heart rate variability",
    "baroreflex",
    "post-exertional malaise",
    "PEM",
    "post exertional",
    "exercise intolerance",
    "exercise capacity",
    "anaerobic threshold",
    "lactate",
    "VO2 max",
    "HPA axis",
    "cortisol",
    "hypothalamic",
    "adrenal",
]

TREAT_TERMS = [
    "treatment",
    "therapy",
    "intervention",
    "management",
    "protocol",
    "drug",
    "medication",
    "pharmacological",
    "non-pharmacological",
    "trial",
    "clinical trial",
    "clinical study",
    "randomized",
    "controlled",
    "rct",
    "phase",
    "pilot",
    "open-label",
    "double-blind",
    "placebo-controlled",
    "sham-controlled",
    "prospective",
    "observational study",
    "efficacy",
    "feasibility",
    "naltrexone",
    "low-dose naltrexone",
    "LDN",
    "ldn",
    "low dose naltrexone",
    "low dose Naltrexone",
    "antiviral",
    "ivermectin",
    "metformin",
    "statin",
    "anticoagulant",
    "antiplatelet",
    "immunomodulator",
    "steroid",
    "corticosteroid",
    "IVIG",
    "monoclonal antibody",
    "fludrocortisone",
    "midodrine",
    "beta blocker",
    "propranolol",
    "ivabradine",
    "pyridostigmine",
    "salt loading",
    "fluid loading",
    "compression garment",
    "compression stockings",
    "exercise training",
    "pacing",
    "activity management",
    "energy envelope",
    "heart rate monitoring",
    "autonomic rehabilitation",
    "rehabilitation",
    "physical therapy",
    "occupational therapy",
    "breathing therapy",
]

NOISE_TERMS = [
    "survey",
    "questionnaire",
    "quality of life",
    "burden",
    "opinion",
    "editorial",
    "commentary",
    "letter to editor",
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

# HTML CARD GENERATION

def build_card_html(p: dict) -> str:
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
            "plrc-scholar": "PLRC",
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

# STATISTICS

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

def inject_badge_stats(stats):
    log("[HTML] Updating badge stats...")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    updated_date = datetime.now().strftime("%Y-%m-%d")

    real_cards = re.findall(r'<div class="paper-card"[\s\S]*?</div>', html)
    total = len(real_cards)

    html = re.sub(
        r'<span id="stat-updated">.*?</span>',
        f'<span id="stat-updated">{updated_date}</span>',
        html
    )

    html = re.sub(
        r'<span id="stat-total-badge">.*?</span>',
        f'<span id="stat-total-badge">{total}</span>',
        html
    )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)

def rebuild_posted_pmids_from_html():
    log("[CLEAN] Rebuilding posted_pmids.txt from index.html...")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    cards = re.findall(r'<div class="paper-card"[\s\S]*?</div>', html)

    real_ids = set()
    for card in cards:
        m = re.search(r'href="([^"]+)"', card)
        if not m:
            continue
        url = m.group(1)
        paper_id = url.split("/")[-1]
        real_ids.add(paper_id)

    cleaned = sorted(real_ids)

    posted_path = os.path.join(REPO_PATH, "posted_pmids.txt")
    with open(posted_path, "w", encoding="utf-8") as f:
        for pid in cleaned:
            f.write(pid + "\n")

    log("[CLEAN] posted_pmids.txt successfully rebuilt.")

# GIT

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

# HTML injection for cards

def inject_cards_into_index(cards_html: str) -> None:
    log("[HTML] Injecting cards into index.html...")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    start = "<!-- SCRAPER_INJECT_START -->"
    end = "<!-- SCRAPER_INJECT_END -->"

    if start not in html or end not in html:
        raise RuntimeError("Inject markers not found in index.html")

    before, middle_and_after = html.split(start, 1)
    existing, after = middle_and_after.split(end, 1)

    existing = existing.strip()
    combined = (existing + "\n\n" + cards_html).strip()

    new_html = before + start + "\n" + combined + "\n" + end + after

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

# MAIN

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

    candidates = [p for p in all_raw if is_valid_candidate(p)]
    log(f"[PREFILTER] Candidates: {len(candidates)}")

    if not candidates:
        log("[AI] No candidates after prefilter.")
        print("\n================ LC SCRAPER END ================\n")
        return

    # PARALLEL AI CLASSIFICATION

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

    # FILTERING (AI + threshold)

    enriched = []
    for p in candidates:
        ai = results.get(p.get("id"))

        if not isinstance(ai, dict):
            continue

        # Huidige logica behouden: LC + category filter
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue

        if not ai.get("long_covid", False):
            continue

        if ai.get("score", 0) < 65:
            continue

        p["ai_score"] = ai.get("score", 0)
        p["ai_category"] = ai.get("category", "Irrelevant")

        raw_group = ai.get("mechanistic_group", "Non-mechanistic") or "Non-mechanistic"
        group = raw_group.lower().replace(" ", "-")
        p["ai_mechanistic_group"] = group

        p["ai_summary"] = ai.get("summary", p.get("abstract", "")[:400])
        p["ai_reason"] = ai.get("reason", "")

        enriched.append(p)

    save_ai_cache(ai_cache)
    log(f"[AI] Selected after filtering (score ≥ 65, LC, category): {len(enriched)}")

    if not enriched:
        log("[DONE] No enriched papers.")
        commit_and_push()
        print("\n================ LC SCRAPER END ================\n")
        return

    # Ranking: score + date
    ranked = sorted(
        enriched,
        key=lambda p: (p.get("ai_score", 0), p.get("date", datetime.min)),
        reverse=True,
    )

    # Top = alles met score ≥ 65 (en al gefilterd)
    top = ranked

    # SECOND PASS: BUILD cached_new FIRST

    log("[CACHE] Checking cached papers for missed relevant items...")

    cached_new = []

    for paper_id, ai in ai_cache.items():
        if paper_id in seen:
            continue
        if not ai.get("long_covid"):
            continue
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue
        if ai.get("score", 0) < 65:
            continue

        original = next((p for p in all_raw if p.get("id") == paper_id), None)
        if not original:
            continue

        if not isinstance(original.get("date"), datetime):
            continue

        original["ai_score"] = ai["score"]
        original["ai_category"] = ai["category"]

        raw_group = ai.get("mechanistic_group", "Non-mechanistic") or "Non-mechanistic"
        group = raw_group.lower().replace(" ", "-")
        original["ai_mechanistic_group"] = group

        original["ai_summary"] = ai["summary"]
        original["ai_reason"] = ai["reason"]

        cached_new.append(original)

    log(f"[CACHE] Missed relevant papers found (score ≥ 65): {len(cached_new)}")

    # BUILD VISIBLE CARDS

    visible_cards = []

    for p in top:
        if build_card_html(p).strip():
            visible_cards.append(p)

    # cached_new alleen gebruiken als er al geposte papers zijn
    use_cached_new = bool(seen)

    if use_cached_new:
        for p in cached_new:
            if build_card_html(p).strip():
                visible_cards.append(p)

    # STATS BASED ON VISIBLE CARDS ONLY

    stats = compute_stats(visible_cards)

    # NEW PAPERS

    new_papers = [p for p in top if p.get("id") not in seen]
    log(f"[NEW] New papers (score ≥ 65, not in seen): {len(new_papers)}")

    if not new_papers and not (use_cached_new and cached_new):
        log("[DONE] No new papers to inject.")
        inject_badge_stats(stats)
        commit_and_push()
        print("\n================ LC SCRAPER END ================\n")
        return

    if use_cached_new:
        all_cards_html = "\n\n".join(build_card_html(p) for p in (new_papers + cached_new))
    else:
        all_cards_html = "\n\n".join(build_card_html(p) for p in new_papers)

    inject_cards_into_index(all_cards_html)
    inject_stats_into_index(stats)
    inject_badge_stats(stats)

    # UPDATE SEEN — ONLY REAL CARDS

    if use_cached_new:
        for p in cached_new:
            if build_card_html(p).strip():
                seen.add(p["id"])

    for p in new_papers:
        if build_card_html(p).strip():
            seen.add(p["id"])

    save_seen(seen)
    rebuild_posted_pmids_from_html()

    commit_and_push()

    log(f"[DONE] Added {len(new_papers)} new papers (plus {len(cached_new) if use_cached_new else 0} cached).")
    print("\n================ LC SCRAPER END ================\n")

if __name__ == "__main__":
    main()
