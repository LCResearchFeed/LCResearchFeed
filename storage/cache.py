import os
import json

# Absolute path to your repo
REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
CACHE_FILE = os.path.join(REPO_PATH, "ai_cache.json")

# ---------------------------------------------------------
# AI Cache Storage
# ---------------------------------------------------------

def load_ai_cache() -> dict:
    """
    Load the AI cache from ai_cache.json.
    Returns a dictionary mapping paper IDs → AI classification results.
    """

    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # If file is corrupted or unreadable, return empty cache
        return {}


def save_ai_cache(cache: dict) -> None:
    """
    Save the AI cache back to ai_cache.json.
    """

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        # Fail silently — lc_scraper.py logs errors separately
        pass
