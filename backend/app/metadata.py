import re
import json
import requests
from thefuzz import fuzz
from flask import current_app


# --- Filename cleaning patterns ---

_BRACKET_RE = re.compile(r"[\[\(][^\]\)]*[\]\)]")
_PUNCT_RE = re.compile(r"[_\-\.]+")
_JUNK_RE = re.compile(
    r"\b(audiobook|ebook|epub|mobi|pdf|m4b|mp3|flac|aac|retail|true|unabridged"
    r"|repack|proper|\d{4})\b",
    re.IGNORECASE,
)
# Leading track numbers: "01 Title", "1 Title", "003 Title"
_LEADING_TRACK_RE = re.compile(r"^\d{1,3}\s+")
# Trailing subtitle noise that's safe to remove
_TRAILING_NOISE_RE = re.compile(
    r"\s*[\-:]?\s*\b(?:a\s+(?:novel|memoir|thriller|novella|story)"
    r"|(?:\d+\w*\s+)?anniversary(?:\s+edition)?)\s*$",
    re.IGNORECASE,
)
# Edition markers in candidate titles from APIs
_EDITION_RE = re.compile(
    r"\s*\([^)]*\b(?:unabridged|abridged|ungek[uü]rzt)\b[^)]*\)\s*$",
    re.IGNORECASE,
)


def _clean(s: str) -> str:
    s = _JUNK_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clean_title(s: str) -> str:
    """Clean a title string and strip trailing subtitle noise."""
    s = _clean(s)
    s = _TRAILING_NOISE_RE.sub("", s).strip()
    return s


def _normalize_candidate_title(title: str) -> str:
    """Strip edition markers like '(Unabridged)' from API-returned titles."""
    return _EDITION_RE.sub("", title).strip()


def parse_torrent_name(name: str) -> dict:
    """Best-effort extraction of author and title from a filename or folder name."""
    # Strip leading track number: "01 For We Are Many" -> "For We Are Many"
    # Only strip 1-3 digits followed by whitespace so we don't touch "1984" etc.
    name = _LEADING_TRACK_RE.sub("", name).strip()

    # Remove bracketed content (series info, format tags, etc.)
    cleaned = _BRACKET_RE.sub(" ", name)
    # Normalize double-dash separator to single
    cleaned = re.sub(r"\s*--+\s*", " - ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Split on " - " BEFORE _PUNCT_RE eats the dash
    if " - " in cleaned:
        parts = [p.strip() for p in cleaned.split(" - ", 1)]
        left = _clean_title(parts[0])
        right = _clean_title(parts[1])
        return _assign_author_title(left, right)

    # Check for "Title by Author" pattern (e.g. "The Burning God by R. F. Kuang")
    by_match = re.search(r"\s+by\s+", cleaned, re.IGNORECASE)
    if by_match:
        left = _clean_title(cleaned[:by_match.start()])
        right = _clean_title(cleaned[by_match.end():])
        # Only treat "by" as separator when left is a plausible title (2+ words)
        # and right is a plausible author name (1-4 words)
        if len(left.split()) >= 2 and 1 <= len(right.split()) <= 4:
            return {"author": right, "title": left}

    return {"author": "", "title": _clean_title(cleaned)}


def _assign_author_title(left: str, right: str) -> dict:
    """
    Heuristic: the shorter part (fewer words) is more likely the author name.
    Special case: a single-word part is more likely a title than an author.
    """
    lw = len(left.split()) if left else 0
    rw = len(right.split()) if right else 0

    # A single-word item is almost certainly a title, not a name
    if lw == 1 and rw > 1:
        return {"author": right, "title": left}
    if rw == 1 and lw > 1:
        return {"author": left, "title": right}

    # Shorter side is more likely the author (names are usually shorter than titles)
    if lw <= rw:
        return {"author": left, "title": right}
    return {"author": right, "title": left}


# --- Scoring ---

def _title_score(parsed_title: str, candidate_title: str) -> float:
    """
    Blend token_sort_ratio and token_set_ratio.
    token_set_ratio handles the case where the parsed title contains the real
    title plus subtitle noise from the filename.  We dampen it when the
    candidate is much shorter than the parsed title to avoid false positives
    from short candidates matching by coincidence.
    """
    a = _normalize_candidate_title(candidate_title)
    b = parsed_title  # already cleaned

    sort_s = fuzz.token_sort_ratio(a, b) / 100
    set_s = fuzz.token_set_ratio(a, b) / 100

    a_words = max(len(a.split()), 1)
    b_words = max(len(b.split()), 1)

    # Don't apply set_ratio boost for very short candidates (1 word risks false positives)
    if min(a_words, b_words) < 2:
        return sort_s

    # Dampen set_ratio proportionally when lengths differ significantly
    length_ratio = min(a_words, b_words) / max(a_words, b_words)
    blended_set = set_s * (0.5 + 0.5 * length_ratio)
    return max(sort_s, blended_set)


def _score(candidate: dict, parsed: dict) -> float:
    title_s = _title_score(parsed.get("title", ""), candidate.get("title", ""))
    author = parsed.get("author", "")

    # When no author was parsed from the filename, use 100% title weight.
    # Penalizing for a missing author would unfairly hurt well-tagged title-only files.
    if not author:
        return title_s

    author_s = fuzz.token_sort_ratio(
        candidate.get("author", ""), author
    ) / 100
    return title_s * 0.65 + author_s * 0.35


# --- Search + score helpers ---

def _search_and_score(author: str, title: str, category: str) -> list:
    """Run the appropriate API search and return scored candidates, best first."""
    query = f"{author} {title}".strip()
    parsed = {"author": author, "title": title}

    if category == "audiobook":
        candidates = _search_audible(query)
        if not candidates:
            candidates = _search_itunes(query)
        if not candidates:
            candidates = _search_googlebooks(query)
    else:
        candidates = _search_openlibrary(query)
        if not candidates:
            candidates = _search_googlebooks(query)

    if not candidates:
        return []

    return sorted(
        [{"score": _score(c, parsed), **c} for c in candidates],
        key=lambda x: x["score"],
        reverse=True,
    )


# --- Metadata API clients ---

def _search_audible(query: str) -> list:
    try:
        resp = requests.get(
            "https://api.audible.com/1.0/catalog/products",
            params={
                "keywords": query,
                "num_results": 5,
                "response_groups": "contributors,product_desc,product_attrs,series",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for product in data.get("products", [])[:5]:
            authors = [a["name"] for a in product.get("authors", []) if a.get("name")]
            series_list = product.get("series", [])
            series = series_list[0].get("title", "") if series_list else ""
            series_seq = series_list[0].get("sequence", "") if series_list else ""
            results.append({
                "title": product.get("title", ""),
                "author": ", ".join(authors),
                "series": series,
                "series_seq": series_seq,
                "source": "audible",
                "raw": product,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"Audible search failed: {e}")
        return []


def _search_itunes(query: str) -> list:
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": query, "media": "audiobook", "entity": "audiobook", "limit": 5},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", [])[:5]:
            title = item.get("trackName") or item.get("collectionName", "")
            results.append({
                "title": title,
                "author": item.get("artistName", ""),
                "series": "",
                "series_seq": "",
                "source": "itunes",
                "raw": item,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"iTunes audiobook search failed: {e}")
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


def resolve_metadata(torrent_name: str, category: str, hint_author: str = "") -> dict:
    """
    Returns:
        {
            "confidence": float,
            "match": {title, author, series, series_seq} or None,
            "candidates": [top 3 with scores]
        }

    hint_author: author string read from file tags — used when none can be
                 parsed from the filename itself.
    """
    parsed = parse_torrent_name(torrent_name)

    # Use file-tag author only when the filename gave us nothing
    if hint_author and not parsed["author"]:
        parsed["author"] = hint_author.strip()

    scored = _search_and_score(parsed["author"], parsed["title"], category)

    # When the filename had a clear Author - Title split, also try the reversed
    # interpretation (Title - Author) and take whichever direction scores higher.
    # This handles cases where the heuristic guessed wrong (e.g. equal word counts,
    # or a short title that looks like a name).
    if parsed["author"] and parsed["title"]:
        flipped = _search_and_score(parsed["title"], parsed["author"], category)
        if flipped and (not scored or flipped[0]["score"] > scored[0]["score"]):
            scored = flipped

    if not scored:
        return {"confidence": 0.0, "match": None, "candidates": []}

    top = scored[0]
    threshold = current_app.config["CONFIDENCE_THRESHOLD"]

    return {
        "confidence": top["score"],
        "match": top if top["score"] >= threshold else None,
        "candidates": scored[:3],
    }
