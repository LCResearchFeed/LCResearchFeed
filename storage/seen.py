import os

# Absolute path to your repo
REPO_PATH = r"C:\Users\mkoni\LCResearchFeed"
SEEN_FILE = os.path.join(REPO_PATH, "posted_pmids.txt")

# ---------------------------------------------------------
# Seen PMIDs storage
# ---------------------------------------------------------

def load_seen() -> set[str]:
    """
    Load the set of PMIDs (or Nature/Science URLs) that have already been posted.
    Returns a Python set of strings.
    """

    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    except Exception:
        # If file is corrupted or unreadable, return empty set
        return set()


def save_seen(seen: set[str]) -> None:
    """
    Save the set of seen PMIDs/IDs back to posted_pmids.txt.
    """

    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            for item in sorted(seen):
                f.write(item + "\n")
    except Exception:
        # Fail silently — lc_scraper.py logs errors separately
        pass
