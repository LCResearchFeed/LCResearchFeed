import json
import requests

from ai.prompts import build_classification_prompt

# ---------------------------------------------------------
# Ollama API call (met harde timeout + veilige fallback)
# ---------------------------------------------------------

def call_ollama(prompt: str) -> str:
    """
    Call the local Ollama model llama3.1:8b.
    Returns raw text from the model, or empty string on failure.
    """

    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False
            },
            timeout=10,  # harde timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")
    except Exception:
        # Bij elke fout (timeout, connectie, JSON) → lege string
        return ""


def extract_json(raw: str) -> dict:
    """
    Extract the first {...} JSON block from the model output.
    If parsing fails, return {}.
    """

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}

        json_str = raw[start:end + 1]
        return json.loads(json_str)

    except Exception:
        return {}


def fallback_classification(p: dict) -> dict:
    """
    If AI fails, return a minimal keyword-based classification.
    """

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


def classify_paper(p: dict, cache: dict) -> dict:
    """
    Classify a paper using llama3.1:8b.
    Uses cache to avoid reprocessing.
    """

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

    # AI-call met harde timeout
    raw = call_ollama(prompt)

    if not raw:
        result = fallback_classification(p)
        cache[cache_key] = result
        return result

    parsed = extract_json(raw)

    if not parsed:
        result = fallback_classification(p)
        cache[cache_key] = result
        return result

    # Defaults afdwingen
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
