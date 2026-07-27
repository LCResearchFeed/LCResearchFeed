import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import subprocess
from datetime import datetime
import concurrent.futures

# Paths
REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
INDEX_PATH = os.path.join(REPO_PATH, "index.html")
LOG_PATH = os.path.join(REPO_PATH, "scheduler_log.txt")

# State
from storage.seen import load_seen, save_seen
from storage.cache import load_ai_cache, save_ai_cache

from utils.deduplicate import deduplicate_papers
from utils.deduplicate import is_duplicate

# Sources
from sources.pubmed import fetch_pubmed_papers
from sources.nature import fetch_nature_papers
from sources.europepmc import fetch_europepmc_papers
from sources.recover import fetch_recover_papers
from sources.patientresearchcovid19 import fetch_plrc_papers
from sources.frontiers import fetch_frontiers_papers
from sources.wust import fetch_wust_papers
from sources.manual import fetch_manual_papers

# AI
from ai.classifier import classify_paper

# ---------------------------------------------------------
# Logging
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
# Prefilter terms
# ---------------------------------------------------------
LC_TERMS = [
    "long covid", "long-covid", "long COVID syndrome", "long COVID condition",
    "post covid", "post-covid", "post-COVID condition", "post COVID condition",
    "post-COVID-19 condition", "PCC", "PASC", "post-acute sequelae",
    "post-acute sequelae of SARS-CoV-2 infection", "post-acute COVID-19 syndrome",
    "post-acute COVID syndrome", "post acute COVID", "post-viral syndrome",
    "post viral syndrome", "post-infectious syndrome", "post infectious syndrome",
    "post-acute infection syndrome", "PAIS", "chronic COVID", "chronic COVID-19",
    "persistent COVID", "persistent COVID-19", "ongoing symptomatic COVID-19",
    "long-term COVID", "post-SARS-CoV-2", "post SARS-CoV-2", "LTC", "LC",
]

MECH_TERMS = [
    "immune", "immunity", "immune dysregulation", "immune dysfunction",
    "inflammation", "inflammatory", "cytokine", "cytokine storm", "interferon",
    "autoimmune", "autoimmunity", "autoantibody", "autoantibodies", "antibody",
    "complement", "mast cell", "mast cell activation", "MCAS", "t-cell", "T cell",
    "b-cell", "B cell", "innate", "adaptive", "NK cell", "natural killer", "viral",
    "virus", "viral persistence", "persistent infection", "persistence", "reservoir",
    "viral reservoir", "reactivation", "latency", "latent", "neurological",
    "neurologic", "neuro", "neuroinflammation", "neuroimmune", "microglia", "glial",
    "blood brain barrier", "BBB", "brain fog", "cognitive dysfunction", "endothelial",
    "endothelium", "endothelial dysfunction", "microclots", "microvascular",
    "vascular", "coagulation", "thrombosis", "platelet", "platelet activation",
    "fibrin", "fibrinogen", "mitochondria", "mitochondrial", "oxidative stress",
    "metabolic", "metabolism", "energy metabolism", "cellular energy", "ATP",
    "autonomic", "autonomic dysfunction", "dysautonomia", "orthostatic intolerance",
    "POTS", "postural tachycardia", "heart rate variability", "baroreflex",
    "post-exertional malaise", "PEM", "post exertional", "exercise intolerance",
    "exercise capacity", "anaerobic threshold", "lactate", "VO2 max", "HPA axis",
    "cortisol", "hypothalamic", "adrenal",
]

TREAT_TERMS = [
    "treatment", "therapy", "intervention", "management", "protocol", "drug",
    "medication", "pharmacological", "non-pharmacological", "trial", "clinical trial",
    "clinical study", "randomized", "controlled", "rct", "phase", "pilot",
    "open-label", "double-blind", "placebo-controlled", "sham-controlled",
    "prospective", "observational study", "efficacy", "feasibility", "naltrexone",
    "low-dose naltrexone", "LDN", "ldn", "low dose naltrexone",
    "low dose Naltrexone", "antiviral", "ivermectin", "metformin", "statin",
    "anticoagulant", "antiplatelet", "immunomodulator", "steroid", "corticosteroid",
    "IVIG", "monoclonal antibody", "fludrocortisone", "midodrine", "beta blocker",
    "propranolol", "ivabradine", "pyridostigmine", "salt loading", "fluid loading",
    "compression garment", "compression stockings", "exercise training", "pacing",
    "activity management", "energy envelope", "heart rate monitoring",
    "autonomic rehabilitation", "rehabilitation", "physical therapy",
    "occupational therapy", "breathing therapy",
]

NOISE_TERMS = [
    "survey", "questionnaire", "quality of life", "burden", "opinion",
    "editorial", "commentary", "letter to editor",
]


def _contains_any(text: str, terms: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in terms)


def _combo(p: dict) -> str:
    """Combine title + abstract safely."""
    title = p.get("title") or ""
    abstract = p.get("abstract") or ""
    return (title + " " + abstract).lower()


# ---------------------------------------------------------
# PubMed / Nature — STRIKT mechanistisch
# ---------------------------------------------------------
def _candidate_pubmed_nature(p: dict) -> bool:
    combo = _combo(p)

    # Must mention LC or COVID
    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    # Must contain mechanistic or treatment terms
    if not (_contains_any(combo, MECH_TERMS) or _contains_any(combo, TREAT_TERMS)):
        return False

    # Noise exclusion
    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


# ---------------------------------------------------------
# EuropePMC — LC-friendly
# ---------------------------------------------------------
def _candidate_europepmc(p: dict) -> bool:
    combo = _combo(p)

    # Must mention LC or COVID
    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    # Noise exclusion
    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


# ---------------------------------------------------------
# Frontiers — ALWAYS send to AI
# ---------------------------------------------------------
def _candidate_frontiers(p: dict) -> bool:
    # Frontiers is mechanistic-heavy → AI decides relevance
    return True


# ---------------------------------------------------------
# Generic sources — LC-friendly
# ---------------------------------------------------------
def _candidate_generic(p: dict) -> bool:
    combo = _combo(p)

    # Must mention LC or COVID
    if not _contains_any(combo, LC_TERMS) and "covid" not in combo:
        return False

    # Noise exclusion
    if _contains_any(combo, NOISE_TERMS):
        return False

    return True


# ---------------------------------------------------------
# Main selector
# ---------------------------------------------------------
def is_valid_candidate(p: dict) -> bool:
    if not isinstance(p.get("date"), datetime):
        return False

    source = (p.get("source") or "").lower()

    if source in ("pubmed", "nature"):
        return _candidate_pubmed_nature(p)

    if source == "europepmc":
        return _candidate_europepmc(p)

    if source == "frontiers":
        return _candidate_frontiers(p)

    return _candidate_generic(p)

# ---------------------------------------------------------
# HTML card generation
# ---------------------------------------------------------
def _source_display_name(s: str) -> str:
    mapping = {
        "pubmed": "PubMed",
        "nature": "Nature",
        "europepmc": "EuropePMC",
        "recover": "RECOVER",
        "plrc-scholar": "PLRC",
        "frontiers": "Frontiers",
        "wust": "Rob Wüst",
        "manual": "Springer Nature",
    }
    return mapping.get(s.lower(), "Other")


def build_card_html(p: dict) -> str:
    if not p.get("title") or not p.get("url"):
        return ""

    abstract = p.get("abstract") or p.get("ai_summary") or "No abstract available."
    source = (p.get("source") or "other").lower()

    category_raw = p.get("ai_category", "") or ""
    category = category_raw.lower()
    group = (p.get("ai_mechanistic_group") or "").lower()

    full_abstract = abstract.replace('"', '&quot;').replace("'", "&#39;")
    ai_summary = (p.get("ai_summary") or "").replace('"', '&quot;').replace("'", "&#39;")

    date_obj = p.get("date")
    date_str = date_obj.strftime("%Y-%m-%d") if isinstance(date_obj, datetime) else ""

    return f"""
<div class="paper-card" data-source="{source}" data-category="{category}" data-mech="{group}">
    <span class="source-badge source-{source}">{_source_display_name(source)}</span>
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

    <p class="abstract hidden" data-full="{full_abstract}">{abstract}</p>

    <a href="{p.get('url','')}" target="_blank">Read paper</a>
</div>
""".strip()


# ---------------------------------------------------------
# Stats
# ---------------------------------------------------------
def compute_stats(papers):
    stats = {"total": len(papers)}
    for p in papers:
        group = (p.get("ai_mechanistic_group") or "").lower()
        stats[group] = stats.get(group, 0) + 1
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
        flags=re.DOTALL,
    )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)

#number of papers on website
def inject_badge_stats(stats):
    log("[HTML] Updating badge stats...")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    updated_date = datetime.now().strftime("%Y-%m-%d")
    real_cards = re.findall(
        r'<div class="paper-card" data-source=.*?>',
        html
    )
    total = len(real_cards)

    html = re.sub(
        r'<span id="stat-updated">.*?</span>',
        f'<span id="stat-updated">{updated_date}</span>',
        html,
    )
    html = re.sub(
        r'<span id="stat-total-badge">.*?</span>',
        f'<span id="stat-total-badge">{total}</span>',
        html,
    )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------
# HTML injection
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Git
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

def clean_duplicate_cards(index_path: str):
    """
    Verwijdert dubbele <div class="paper-card"> blokken uit index.html
    op basis van DOI, PMID, URL en titel.
    Gebruikt dezelfde logica als is_duplicate().
    Geeft: {"removed": X, "remaining": Y, "stats": {...}}.
    """

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    start = "<!-- SCRAPER_INJECT_START -->"
    end = "<!-- SCRAPER_INJECT_END -->"

    if start not in html or end not in html:
        raise RuntimeError("Inject markers not found in index.html")

    before, middle_and_after = html.split(start, 1)
    inject_block, after = middle_and_after.split(end, 1)

    inject_block = inject_block.strip()

    # ---------------------------------------------------------
    # 1. Vind alle kaart-startposities
    # ---------------------------------------------------------
    card_starts = []
    pos = 0
    while True:
        idx = inject_block.find('<div class="paper-card"', pos)
        if idx == -1:
            break
        card_starts.append(idx)
        pos = idx + 1

    if not card_starts:
        return {"removed": 0, "remaining": 0, "stats": {"total": 0}}

    # ---------------------------------------------------------
    # 2. Snijd elke kaart uit het inject-blok
    # ---------------------------------------------------------
    card_html_list = []

    for i, start_idx in enumerate(card_starts):
        end_idx = card_starts[i + 1] if i + 1 < len(card_starts) else len(inject_block)
        card_html = inject_block[start_idx:end_idx].strip()
        card_html_list.append(card_html)

    # ---------------------------------------------------------
    # 3. Parse metadata uit elke kaart
    # ---------------------------------------------------------
    parsed = []

    for card_html in card_html_list:
        url_match = re.search(r'<a href="([^"]+)"', card_html)
        url = url_match.group(1).strip() if url_match else ""

        title_match = re.search(r'<h2>(.*?)</h2>', card_html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        doi_match = re.search(r'doi[:/]\s*([^\s"<]+)', card_html, re.IGNORECASE)
        doi = doi_match.group(1).strip() if doi_match else ""

        pmid_match = re.search(r'pmid[:/]\s*([0-9]+)', card_html, re.IGNORECASE)
        pmid = pmid_match.group(1).strip() if pmid_match else ""

        source_match = re.search(r'data-source="([^"]+)"', card_html)
        source = source_match.group(1).strip() if source_match else ""

        mech_match = re.search(r'data-mech="([^"]+)"', card_html)
        mech = mech_match.group(1).strip().lower() if mech_match else "unknown"

        parsed.append({
            "html": card_html,
            "url": url,
            "title": title,
            "doi": doi,
            "pmid": pmid,
            "source": source,
            "ai_mechanistic_group": mech,
        })

    # ---------------------------------------------------------
    # 4. Deduplicatie met jouw is_duplicate()
    # ---------------------------------------------------------
    unique = []
    removed = 0

    for p in parsed:
        duplicate_index = None
        for i, existing in enumerate(unique):
            if is_duplicate(p, existing):
                duplicate_index = i
                break

        if duplicate_index is None:
            unique.append(p)
        else:
            removed += 1

    # ---------------------------------------------------------
    # 5. Nieuwe inject-blok opbouwen
    # ---------------------------------------------------------
    cleaned_cards_html = "\n\n".join(p["html"] for p in unique)

    new_html = before + start + "\n" + cleaned_cards_html + "\n" + end + after

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    # ---------------------------------------------------------
    # 6. Stats bouwen
    # ---------------------------------------------------------
    stats = {"total": len(unique)}
    for p in unique:
        group = (p.get("ai_mechanistic_group") or "").lower()
        stats[group] = stats.get(group, 0) + 1

    return {
        "removed": removed,
        "remaining": len(unique),
        "stats": stats,
    }


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
def main() -> None:
    print("\n================ LC SCRAPER START ================\n")

    seen = load_seen()
    ai_cache = load_ai_cache()

    sources = {
        "pubmed": fetch_pubmed_papers(),
        "nature": fetch_nature_papers(),
        "europepmc": fetch_europepmc_papers(),
        "recover": fetch_recover_papers(),
        "patientresearchcovid19": fetch_plrc_papers(),
        "frontiers": fetch_frontiers_papers(),
        "wust": fetch_wust_papers(),
        "manual": fetch_manual_papers(),
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

        result = clean_duplicate_cards(INDEX_PATH)

        inject_stats_into_index(result["stats"])
        inject_badge_stats(result["stats"])

        commit_and_push()

        print("\n================ LC SCRAPER END ================\n")
        return

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

    enriched = []
    for p in candidates:
        ai = results.get(p["id"])
        if not isinstance(ai, dict):
            continue
        if ai.get("category") in ("Irrelevant", "Epidemiology"):
            continue
        if not ai.get("long_covid", False):
            continue
        if p.get("source") != "manual" and ai.get("score", 0) < 65:
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
    
    before = len(enriched)

    enriched = deduplicate_papers(enriched)

    after = len(enriched)

    log(
        f"[DEDUP] Removed {before-after} duplicate papers. "
        f"Remaining: {after}"
    )

    if not enriched:
        log("[DONE] No enriched papers.")

        result = clean_duplicate_cards(INDEX_PATH)

        inject_stats_into_index(result["stats"])
        inject_badge_stats(result["stats"])

        commit_and_push()

        print("\n================ LC SCRAPER END ================\n")
        return

    ranked = sorted(
        enriched,
        key=lambda p: (p.get("ai_score", 0), p.get("date", datetime.min)),
        reverse=True,
    )
    top = ranked

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

    use_cached_new = bool(seen)

    new_papers = [p for p in top if p.get("id") not in seen]
    log(f"[NEW] New papers (score ≥ 65, not in seen): {len(new_papers)}")

    if not new_papers and not (use_cached_new and cached_new):
        log("[DONE] No new papers to inject.")

        result = clean_duplicate_cards(INDEX_PATH)

        inject_stats_into_index(result["stats"])
        inject_badge_stats(result["stats"])

        commit_and_push()
        print("\n================ LC SCRAPER END ================\n")
        return

    if use_cached_new:
        all_cards_html = "\n\n".join(
            build_card_html(p) for p in (new_papers + cached_new)
        )
    else:
        all_cards_html = "\n\n".join(build_card_html(p) for p in new_papers)

    inject_cards_into_index(all_cards_html)


    # ---------------------------------------------------------
    # FINAL HTML DEDUPLICATION
    # ---------------------------------------------------------

    result = clean_duplicate_cards(INDEX_PATH)
    
    stats = result["stats"]

    log(
        f"[HTML DEDUP] Removed {result['removed']} duplicates. "
        f"Remaining cards: {result['remaining']}"
    )

    inject_stats_into_index(stats)
    inject_badge_stats(stats)

    if use_cached_new:
        for p in cached_new:
            if build_card_html(p).strip():
                seen.add(p["id"])

    for p in new_papers:
        if build_card_html(p).strip():
            seen.add(p["id"])

    save_seen(seen)

    commit_and_push()

    log(
        f"[DONE] Added {len(new_papers)} new papers"
        f" (plus {len(cached_new) if use_cached_new else 0} cached)."
    )
    print("\n================ LC SCRAPER END ================\n")


if __name__ == "__main__":
    main()
