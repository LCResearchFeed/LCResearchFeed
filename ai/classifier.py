import json
import time
import requests
import concurrent.futures
import re

from ai.prompts import build_classification_prompt


API_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-7b-instruct"


# ---------------------------------------------------------
# AI agent call
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
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return ""


# ---------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------

def extract_json(raw: str) -> dict:
    if not raw:
        return {}

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    json_str = raw[start:end + 1]

    try:
        return json.loads(json_str)
    except Exception:
        pass

    cleaned = (
        json_str
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )

    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        return {}


# ---------------------------------------------------------
# Fallback classification
# ---------------------------------------------------------

def fallback_classification(p: dict) -> dict:
    abstract = p["abstract"].lower()
    title = p["title"].lower()

    mech_keywords = ["immune", "inflammation", "mitochondria", "viral", "persistent"]
    treat_keywords = ["treatment", "therapy", "drug", "trial", "intervention"]

    mechanism = any(k in abstract or k in title for k in mech_keywords)
    treatment = any(k in abstract or k in title for k in treat_keywords)

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
        mechanistic_group = "Irrelevant"

    if mechanism:
        category = mechanistic_group
    elif treatment:
        category = "Treatment"
    else:
        category = "Irrelevant"

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
# Main classifier (single paper)
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

    parsed.setdefault("score", 0)
    parsed.setdefault("category", "Irrelevant")
    parsed.setdefault("long_covid", False)
    parsed.setdefault("mechanistic_group", "Irrelevant")

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
# Parallel classification (NEW)
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
