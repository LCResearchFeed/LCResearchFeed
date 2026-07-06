import json
import requests

from ai.prompts import build_classification_prompt

# ---------------------------------------------------------
# Ollama API call (Qwen2.5-Coder-14B)
# ---------------------------------------------------------

def call_ollama(prompt: str) -> str:
    """
    Call the local Ollama model qwen2.5-coder:14b.
    Returns raw text from the model, or empty string on failure.
    """

    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma:7b-instruct",
                "prompt": prompt,
                "stream": True
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")
    except Exception:
        return ""


# ---------------------------------------------------------
# JSON extraction (robust)
# ---------------------------------------------------------

def extract_json(raw: str) -> dict:
    if not raw:
        return {}

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    json_str = raw[start:end + 1]

    # First attempt
    try:
        return json.loads(json_str)
    except Exception:
        pass

    # Cleanup
    cleaned = (
        json_str
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )

    # Remove markdown fences
    import re
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)

    # Remove trailing commas
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

    category = "Mechanism" if mechanism else "Treatment" if treatment else "Irrelevant"
    score = 70 if mechanism or treatment else 20

    return {
        "score": score,
        "category": category,
        "long_covid": "long covid" in abstract or "long covid" in title,
        "mechanism": mechanism,
        "treatment": treatment,
        "drug": False,
        "lifestyle": False,
        "review": False,
        "summary": p["abstract"][:400],
        "reason": "Fallback classification due to AI failure or timeout."
    }


# ---------------------------------------------------------
# Main classifier
# ---------------------------------------------------------

def classify_paper(p: dict, cache: dict) -> dict:
    cache_key = p["id"]

    # Cache hit
    if cache_key in cache:
        return cache[cache_key]

    prompt = build_classification_prompt(
        title=p["title"],
        abstract=p["abstract"],
        source=p["source"],
        url=p["url"]
    )

    # First AI call
    raw = call_ollama(prompt)
    parsed = extract_json(raw)

    # Retry ONLY if JSON is completely empty
    if not parsed:
        print(f"Retrying classification for {cache_key}...")
        raw_retry = call_ollama(prompt)
        parsed_retry = extract_json(raw_retry)
        if parsed_retry:
            parsed = parsed_retry

    # Fallback if still empty
    if not parsed:
        result = fallback_classification(p)
        cache[cache_key] = result
        return result

    # Enforce defaults
    parsed.setdefault("score", 0)
    parsed.setdefault("category", "Irrelevant")
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
