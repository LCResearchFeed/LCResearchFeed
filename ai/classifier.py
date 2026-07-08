import json
import time
import requests
import concurrent.futures
import re

from ai.prompts import build_classification_prompt


API_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-7b-instruct"


# ---------------------------------------------------------
# AI agent call — FULLY FIXED
# ---------------------------------------------------------

def call_agent(prompt: str) -> str:
    try:
        resp = requests.post(
            API_URL,
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=120,
        )
        resp.raise_for_status()

        data = resp.json()

        # Extract ONLY the assistant content
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("AI ERROR:", e)
        return ""


# ---------------------------------------------------------
# JSON extraction — FULLY FIXED
# ---------------------------------------------------------

def extract_json(raw: str) -> dict:
    if not raw:
        return {}

    # Remove markdown fences if present
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Find first { and last }
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        json_str = raw[start:end]
    except ValueError:
        return {}

    # Try direct JSON load
    try:
        return json.loads(json_str)
    except Exception:
        pass

    # Cleanup fallback
    cleaned = (
        json_str
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )

    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        return {}


# ---------------------------------------------------------
# Fallback classification (unchanged)
# ---------------------------------------------------------

def fallback_classification(p: dict) -> dict:
    abstract = p["abstract"].lower()
    title = p["title"].lower()

    mech_keywords = ["immune", "inflammation", "mitochondria", "viral", "persistent"]
    treat_keywords = ["treatment", "therapy", "drug", "trial", "intervention"]

    mechanism = any(k in abstract or k in title for k in mech_keywords)
    treatment = any(k in abstract or k in title for k in treat_keywords)

    if mechanism:
        if "viral" in abstract or "persistent" in abstract:
            mechanistic_group = "Viral Persistence"
        elif "auto" in abstract or "immune" in abstract:
            mechanistic_group = "Autoimmunity"
        elif "pots" in abstract or "dysaut" in abstract:
            mechanistic_group = "Dysautonomia"
        elif "micro" in abstract or "vascular" in abstract:
            mechanistic_group = "Microvascular"
        elif "mito" in abstract:
            mechanistic_group = "Mitochondrial"
        else:
            mechanistic_group = "Non-mechanistic"
    else:
        mechanistic_group = "Non-mechanistic"

    if "review" in abstract:
        category = "Review"
    elif "lifestyle" in abstract:
        category = "Lifestyle"
    elif "drug" in abstract:
        category = "Drug"
    elif treatment:
        category = "Treatment"
    elif mechanism:
        category = "Mechanism"
    else:
        category = "Mechanism"

    score = 75 if mechanism or treatment else 20

    return {
        "score": score,
        "category": category,
        "long_covid": "long covid" in abstract or "long covid" in title,
        "mechanistic_group": mechanistic_group,
        "mechanism": mechanism,
        "treatment": treatment,
        "drug": "drug" in abstract,
        "lifestyle": "lifestyle" in abstract,
        "review": "review" in abstract,
        "summary": p["abstract"][:400],
        "reason": "Fallback classification due to AI failure or timeout."
    }


# ---------------------------------------------------------
# Main classifier — FULLY FIXED
# ---------------------------------------------------------

def classify_paper(p: dict, cache: dict) -> dict:
    cache_key = p["id"]

    if cache_key in cache:
        return cache[cache_key]

    prompt = build_classification_prompt(
        title=p["title"],
        abstract=p["abstract"],
        source=p["source"],
        url=p["url"]
    )

    raw = call_agent(prompt)
    parsed = extract_json(raw)

    if not parsed:
        raw_retry = call_agent(prompt)
        parsed_retry = extract_json(raw_retry)
        if parsed_retry:
            parsed = parsed_retry

    if not parsed:
        result = fallback_classification(p)
        cache[cache_key] = result
        return result

    valid_categories = {"Mechanism", "Treatment", "Drug", "Lifestyle", "Review"}
    valid_groups = {
        "Viral Persistence", "Autoimmunity", "Dysautonomia",
        "Microvascular", "Mitochondrial", "Non-mechanistic"
    }

    if parsed.get("category") not in valid_categories:
        if parsed.get("review"):
            parsed["category"] = "Review"
        elif parsed.get("lifestyle"):
            parsed["category"] = "Lifestyle"
        elif parsed.get("drug"):
            parsed["category"] = "Drug"
        elif parsed.get("treatment"):
            parsed["category"] = "Treatment"
        elif parsed.get("mechanism"):
            parsed["category"] = "Mechanism"
        else:
            parsed["category"] = "Mechanism"

    if parsed.get("mechanistic_group") not in valid_groups:
        parsed["mechanistic_group"] = "Non-mechanistic"

    parsed.setdefault("score", 0)
    parsed.setdefault("long_covid", False)
    parsed.setdefault("mechanism", False)
    parsed.setdefault("treatment", False)
    parsed.setdefault("drug", False)
    parsed.setdefault("lifestyle", False)
    parsed.setdefault("review", False)
    parsed.setdefault("summary", p["abstract"][:400])
    parsed.setdefault("reason", "")

    cache[cache_key] = parsed
    return parsed


# ---------------------------------------------------------
# Parallel classification
# ---------------------------------------------------------

def classify_parallel(papers: list, cache: dict, workers: int = 6) -> dict:
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(classify_paper, p, cache): p["id"]
            for p in papers
        }

        for future in concurrent.futures.as_completed(future_map):
            pid = future_map[future]
            try:
                results[pid] = future.result()
            except Exception as e:
                results[pid] = {"error": str(e)}

    return results
