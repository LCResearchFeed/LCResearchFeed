import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs


def normalize_title(title: str) -> str:
    if not title:
        return ""

    title = title.lower()
    title = re.sub(r"&\w+;", " ", title)
    title = "".join(c for c in title if c.isalnum() or c.isspace())
    return " ".join(title.split())


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""

    doi = doi.lower().strip()

    # strip common prefixes
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/)", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)

    # strip suffixes
    doi = re.sub(r"/(pdf|epdf|abstract)$", "", doi)

    # strip query params
    doi = doi.split("?")[0]

    return doi


def normalize_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    parsed = urlparse(url)

    # strip query params & fragments
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    return clean.rstrip("/").lower()


def normalize_id(value):
    if not value:
        return ""

    v = str(value).strip().lower()

    # unify pubmed
    if v.startswith("pubmed-"):
        return v.replace("pubmed-", "")

    # unify pmcid
    if v.startswith("pmcid:"):
        return v.replace("pmcid:", "").strip()

    # unify europepmc DOI
    if v.startswith("europepmc-10."):
        return v.replace("europepmc-", "")

    return v


def same_title(a: str, b: str, threshold=0.86):
    a = normalize_title(a)
    b = normalize_title(b)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def is_duplicate(paper, existing):

    # PMID
    if paper.get("pmid") and existing.get("pmid"):
        if normalize_id(paper["pmid"]) == normalize_id(existing["pmid"]):
            return True

    # DOI
    if paper.get("doi") and existing.get("doi"):
        if normalize_doi(paper["doi"]) == normalize_doi(existing["doi"]):
            return True

    # URL
    if paper.get("url") and existing.get("url"):
        if normalize_url(paper["url"]) == normalize_url(existing["url"]):
            return True

    # Generic ID
    if paper.get("id") and existing.get("id"):
        if normalize_id(paper["id"]) == normalize_id(existing["id"]):
            return True

    # Title
    if same_title(paper.get("title", ""), existing.get("title", "")):
        return True

    return False


def paper_quality(paper):
    score = 0
    if paper.get("abstract"): score += 2
    if paper.get("doi"): score += 2
    if paper.get("pmid"): score += 2
    if paper.get("ai_summary"): score += 1
    return score


def deduplicate_papers(papers):
    unique = []
    removed = 0

    for paper in papers:
        duplicate_index = None

        for i, existing in enumerate(unique):
            if is_duplicate(paper, existing):
                duplicate_index = i
                break

        if duplicate_index is None:
            unique.append(paper)
        else:
            old = unique[duplicate_index]
            if paper_quality(paper) > paper_quality(old):
                unique[duplicate_index] = paper
            removed += 1

    return unique
