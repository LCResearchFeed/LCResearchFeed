import json
import requests
import concurrent.futures

from ai.prompts import build_classification_prompt

API_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-7b-instruct"


# ---------------------------------------------------------
# JSON extraction — strict, no fallback
# ---------------------------------------------------------
import re

def robust_extract_json(raw: str) -> dict:
    if not raw:
        return {}

    # Strip control characters (incl. BOM, null bytes)
    raw = re.sub(r'[\x00-\x1F\x7F]', '', raw).strip()

    try:
        return json.loads(raw)
    except Exception:
        # Als er meer '{' dan '}' zijn → één '}' toevoegen
        if raw.count('{') > raw.count('}'):
            try:
                return json.loads(raw + '}')
            except Exception:
                return {}
        return {}

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
            timeout=1200,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("AI ERROR:", e)
        return ""


# ---------------------------------------------------------
# Main classifier — NO FALLBACK
# ---------------------------------------------------------

def classify_paper(p: dict, cache: dict) -> dict | None:
    cache_key = p["id"]

    # Cache hit
    if cache_key in cache:
        cached = cache[cache_key]

        required = {
            "score", "category", "long_covid", "mechanistic_group",
            "mechanism", "treatment", "drug", "lifestyle", "review",
            "summary", "reason"
        }

        if all(k in cached for k in required):
            return cached

        print(f"[AI] Reclassifying corrupted cache entry: {cache_key}")

    # Build prompt
    prompt = build_classification_prompt(
        title=p["title"],
        abstract=p["abstract"],
        source=p["source"],
        url=p["url"]
    )

    # First attempt
    raw = call_agent(prompt)

    # DEBUG
    print("\n================ RAW AI OUTPUT ================")
    print(f"Paper ID: {p['id']}")
    print(raw)
    print("================================================\n")

    parsed = robust_extract_json(raw)

    # Retry once
    if not parsed:
        raw_retry = call_agent(prompt)
        parsed_retry = robust_extract_json(raw_retry)
        if parsed_retry:
            parsed = parsed_retry

    # Still invalid → skip
    if not parsed:
        print(f"[AI] JSON parse failed for paper {p['id']}, skipping.")
        return None

    # ---------------------------------------------------------
    # Schema validation — skip if missing fields
    # ---------------------------------------------------------

    required_fields = {
        "score", "category", "long_covid", "mechanistic_group",
        "mechanism", "treatment", "drug", "lifestyle", "review",
        "summary", "reason"
    }

    if not all(k in parsed for k in required_fields):
        print(f"[AI] Schema validation failed for paper {p['id']}, skipping.")
        return None

    # ---------------------------------------------------------
    # Type validation — skip if wrong types
    # ---------------------------------------------------------

    if not isinstance(parsed["score"], int):
        print(f"[AI] Invalid score type for paper {p['id']}, skipping.")
        return None

    if not isinstance(parsed["long_covid"], bool):
        print(f"[AI] Invalid long_covid type for paper {p['id']}, skipping.")
        return None

    # Case-insensitive category validation
    valid_categories = {"Mechanism", "Treatment", "Drug", "Lifestyle", "Review"}
    if parsed["category"].lower() not in {c.lower() for c in valid_categories}:
        print(f"[AI] Invalid category for paper {p['id']}, skipping.")
        return None

    # Case-insensitive mechanistic group validation
    valid_groups = {
        "Viral Persistence", "Autoimmunity", "Dysautonomia",
        "Microvascular", "Mitochondrial", "Neuroinflammation",
        "Non-mechanistic", "Immune Dysregulation"
    }

    if parsed["mechanistic_group"].lower() not in {g.lower() for g in valid_groups}:
        print(f"[AI] Invalid mechanistic_group for paper {p['id']}, skipping.")
        return None

    # ---------------------------------------------------------
    # Save valid result
    # ---------------------------------------------------------

    cache[cache_key] = parsed
    return parsed

# ---------------------------------------------------------
# Parallel classification
# ---------------------------------------------------------

def classify_parallel(papers: list, cache: dict, workers: int = 1) -> dict:
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