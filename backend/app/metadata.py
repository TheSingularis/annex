import re
import json
import requests
from thefuzz import fuzz
from flask import current_app


# --- Torrent name parsing ---

_JUNK_RE = re.compile(
    r"\b(audiobook|ebook|epub|mobi|pdf|m4b|mp3|flac|aac|retail|true|unabridged"
    r"|repack|proper|\d{4})\b",
    re.IGNORECASE,
)
_BRACKET_RE = re.compile(r"[\[\(][^\]\)]*[\]\)]")
_PUNCT_RE = re.compile(r"[_\-\.]+")


def parse_torrent_name(name: str) -> dict:
    """Best-effort extraction of author and title from a torrent name."""
    cleaned = _BRACKET_RE.sub(" ", name)
    cleaned = _JUNK_RE.sub(" ", cleaned)
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Common pattern: "Author Name - Title" or "Title - Author Name"
    if " - " in cleaned:
        parts = [p.strip() for p in cleaned.split(" - ", 1)]
        # Heuristic: shorter part is more likely the author (names are short)
        if len(parts[0].split()) <= 3:
            return {"author": parts[0], "title": parts[1]}
        return {"author": parts[1], "title": parts[0]}

    return {"author": "", "title": cleaned}


# --- Metadata clients ---

def _score(candidate: dict, parsed: dict) -> float:
    title_score = fuzz.token_sort_ratio(
        candidate.get("title", ""), parsed.get("title", "")
    ) / 100
    author_score = fuzz.token_sort_ratio(
        candidate.get("author", ""), parsed.get("author", "")
    ) / 100
    # Weight title more heavily than author
    return title_score * 0.65 + author_score * 0.35


def _search_audnexus(query: str) -> list:
    try:
        resp = requests.get(
            "https://api.audnex.us/books",
            params={"query": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data[:5]:
            results.append({
                "title": item.get("title", ""),
                "author": ", ".join(
                    [a.get("name", "") for a in item.get("authors", [])]
                ),
                "series": item.get("seriesPrimary", {}).get("name", "") if item.get("seriesPrimary") else "",
                "series_seq": str(item.get("seriesPrimary", {}).get("position", "")) if item.get("seriesPrimary") else "",
                "source": "audnexus",
                "raw": item,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"Audnexus search failed: {e}")
        return []


def _search_openlibrary(query: str) -> list:
    try:
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": 5},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for doc in data.get("docs", [])[:5]:
            results.append({
                "title": doc.get("title", ""),
                "author": ", ".join(doc.get("author_name", [])),
                "series": "",
                "series_seq": "",
                "source": "openlibrary",
                "raw": doc,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"OpenLibrary search failed: {e}")
        return []


def _search_googlebooks(query: str) -> list:
    try:
        resp = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": 5},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("items", [])[:5]:
            info = item.get("volumeInfo", {})
            results.append({
                "title": info.get("title", ""),
                "author": ", ".join(info.get("authors", [])),
                "series": "",
                "series_seq": "",
                "source": "googlebooks",
                "raw": info,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"Google Books search failed: {e}")
        return []


def resolve_metadata(torrent_name: str, category: str) -> dict:
    """
    Returns:
        {
            "confidence": float,
            "match": {title, author, series, series_seq} or None,
            "candidates": [top 3 with scores]
        }
    """
    parsed = parse_torrent_name(torrent_name)
    query = f"{parsed['author']} {parsed['title']}".strip()

    if category == "audiobook":
        candidates = _search_audnexus(query)
    else:
        candidates = _search_openlibrary(query)
        if not candidates:
            candidates = _search_googlebooks(query)

    if not candidates:
        return {"confidence": 0.0, "match": None, "candidates": []}

    scored = sorted(
        [{"score": _score(c, parsed), **c} for c in candidates],
        key=lambda x: x["score"],
        reverse=True,
    )

    top = scored[0]
    threshold = current_app.config["CONFIDENCE_THRESHOLD"]

    return {
        "confidence": top["score"],
        "match": top if top["score"] >= threshold else None,
        "candidates": scored[:3],
    }
