import re
import json
import time
import requests
from thefuzz import fuzz
from flask import current_app

from app.matching import scoring


# --- Filename cleaning patterns ---

_BRACKET_RE = re.compile(r"[\[\(][^\]\)]*[\]\)]")
_PUNCT_RE = re.compile(r"[,_\-\.]+")
_JUNK_RE = re.compile(
    r"\b(audiobook|ebook|epub|mobi|azw3?|pdf|m4b|mp3|flac|aac|retail|true|unabridged"
    r"|repack|proper|cbz|cbr|cb7|cbt|digital|scan|\d{4})\b",
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

# OpenLibrary's search.json returns zero results for some otherwise-findable
# combined author+title queries when the query contains a straight or curly
# apostrophe -- verified empirically against a real title ("Moss'd in
# Space" by Rebecca Thorne): the title-only query "Moss'd in Space" finds it
# fine, but the combined query "Rebecca Thorne Moss'd in Space" (what
# _search_and_score actually sends) returns nothing, while the same combined
# query with the apostrophe stripped ("Rebecca Thorne Mossd in Space")
# matches instantly. Scoped to the query string sent over the wire only --
# the parsed title used for scoring keeps the apostrophe untouched.
_QUERY_APOSTROPHE_RE = re.compile(r"[‘’']")


def _sanitize_query(query: str) -> str:
    return _QUERY_APOSTROPHE_RE.sub("", query)

# Release groups sometimes swap ':' for a lookalike character to dodge
# filesystem restrictions (e.g. "Heir of Fire꞉ Throne of Glass, Book 3").
# Normalize those back to a real colon so downstream colon-based logic
# (subtitle splitting, the book-marker pattern below) still sees them.
_COLON_SUBSTITUTES = "꞉："

# A bracketed aside naming the series and book number, e.g.
# "(The Three-Body Problem, Book 3)" or "(Throne of Glass Book 3)".
_BOOK_MARKER_RE = re.compile(
    r"^(?P<series>.+?),?\s+book\s+(?P<seq>\d+(?:\.\d+)?)$", re.IGNORECASE
)
# A whole dash-delimited segment that's just "<series name> <number>", e.g.
# "Zodiac Academy 07" in "Author - Zodiac Academy 07 - Title" -- the
# release-name convention for a series entry.
_SEGMENT_SERIES_RE = re.compile(r"^(?P<series>.+?)\s+(?P<seq>\d{1,3}(?:\.\d+)?)$")

# Segments that are noise, not title/author content, when they show up as the
# middle or trailing segment of an otherwise-unresolved 3-way dash split (e.g.
# "The Mask Falling - Author's preferred text - Samantha Shannon", "Roadside
# Picnic - Arkady Strugatsky - trans Bormashenko"). Curated from real
# needs_review filenames (2026-07-21) -- expected to need extending over
# time, same as the Phase 3 summary-mill blocklist.
_CREDIT_MARKER_RE = re.compile(
    r"^(?:trans(?:lated\s+by)?|read\s+by|narrated\s+by)\s+.+$", re.IGNORECASE
)
_NOISE_PHRASE_RE = re.compile(
    r"^(?:author'?s\s+preferred\s+text|corrected|unabridged|abridged)$", re.IGNORECASE
)
# ISBN-10/13-shaped bare digit run left over after a filename tacks on an
# identifier as its own dash segment. This doesn't extract or use the ISBN
# (that's app.matching.identifiers's job, not yet wired into this parser) --
# it only keeps the digits from being merged into the title/author text.
_IDENTIFIER_SEGMENT_RE = re.compile(r"^\d{9,13}(?:\.[A-Za-z0-9]{2,4})?$")


def _is_noise_segment(segment: str) -> bool:
    segment = segment.strip()
    return bool(
        _CREDIT_MARKER_RE.match(segment)
        or _NOISE_PHRASE_RE.match(segment)
        or _IDENTIFIER_SEGMENT_RE.match(segment)
    )


# Common Audible-style naming with no dash at all: "Title: Series, Book N"
# (e.g. "Heir of Fire: Throne of Glass, Book 3"). No author in this
# convention -- it comes from file tags instead, via resolve_metadata's
# hint_author.
#
# Separator is ':' or a single '_' -- downloaders that can't put a literal
# ':' in a filename (Windows-illegal) sometimes substitute '_' instead of
# one of the unicode lookalikes _COLON_SUBSTITUTES already handles (verified
# real example: "Moss'd in Space_  Moss'd in Space, Book 1.m4b", the real
# title being "Moss'd in Space: Moss'd in Space, Book 1"). Scoped to this
# regex only, not added to _COLON_SUBSTITUTES's blanket string-wide
# replacement -- '_' is already overloaded as a generic word-separator
# elsewhere (the "Author_-_Title" convention), so a global substitution
# would corrupt those cases instead.
_COLON_SERIES_RE = re.compile(
    r"^(?P<title>.+?)[_:]\s*(?P<series>.+?),?\s+book\s+(?P<seq>\d+(?:\.\d+)?)"
    r"(?:\.[A-Za-z0-9]{2,4})?\s*$",
    re.IGNORECASE,
)

# Comic/manga volume, chapter, or issue markers: "Vol. 3", "v03", "Chapter 12", "#7"
_VOLUME_RE = re.compile(r"\bv(?:ol(?:ume)?)?\.?\s*0*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"\bch(?:apter)?\.?\s*0*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_ISSUE_RE = re.compile(r"#\s*0*(\d+(?:\.\d+)?)\b")


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
    """Best-effort extraction of author, title, and series/number from a filename or folder name."""
    # Strip leading track number: "01 For We Are Many" -> "For We Are Many"
    # Only strip 1-3 digits followed by whitespace so we don't touch "1984" etc.
    name = _LEADING_TRACK_RE.sub("", name).strip()
    for ch in _COLON_SUBSTITUTES:
        name = name.replace(ch, ":")

    colon_match = _COLON_SERIES_RE.match(name)
    if colon_match:
        return {
            "author": "",
            "title": _clean_title(colon_match.group("title")),
            "series": _clean(colon_match.group("series")),
            "series_seq": colon_match.group("seq"),
        }

    series, series_seq = "", ""

    # Series/book info embedded in a bracketed aside, e.g. "Death's End (The
    # Three-Body Problem, Book 3)" -- must be captured before _BRACKET_RE
    # below discards the bracket contents entirely.
    for bracket in _BRACKET_RE.finditer(name):
        inner = bracket.group(0)[1:-1].strip()
        m = _BOOK_MARKER_RE.match(inner)
        if m:
            series, series_seq = m.group("series").strip(), m.group("seq")
            break

    # Remove bracketed content (series info, format tags, etc.)
    cleaned = _BRACKET_RE.sub(" ", name)
    # Underscores are a common word-separator convention in release names
    # ("Author_-_Title.epub"); normalize to spaces before the " - " split
    # check below, otherwise that whole naming convention never matches it.
    cleaned = cleaned.replace("_", " ")
    # Normalize double-dash separator to single
    cleaned = re.sub(r"\s*--+\s*", " - ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Split on " - " BEFORE _PUNCT_RE eats the dash
    if " - " in cleaned:
        segments = [s.strip() for s in cleaned.split(" - ")]

        # Release convention: "Author - Series NN - Title", or the reverse
        # "Series NN - Title - Author". A segment (other than the very last)
        # matching "<name> <N>" names a series entry rather than being part
        # of the author/title. Requires 3+ segments (a real author segment
        # present) -- with only 2 segments this is too ambiguous to guess
        # (e.g. "Fahrenheit 451 - A Novel" is a title with a number in it,
        # not series "Fahrenheit" book 451).
        series_at_start = False
        series_from_segment = False
        if not series and len(segments) >= 3:
            for i in range(len(segments) - 1):
                m = _SEGMENT_SERIES_RE.match(segments[i])
                if m:
                    series, series_seq = m.group("series").strip(), m.group("seq")
                    series_at_start = i == 0
                    series_from_segment = True
                    del segments[i]
                    break

        if series_from_segment:
            # The series segment carried the ambiguity; whatever's left
            # keeps its original relative order, so no need to re-run the
            # word-count heuristic below on the remainder. "Series NN -
            # Title - Author" leaves [Title, Author]; "Author - Series NN -
            # Title" leaves [Author, ..., Title]. (A series found via the
            # bracketed-aside case above carries no such positional info,
            # so it still falls through to the heuristic below.)
            if series_at_start and len(segments) >= 2:
                result = {
                    "author": _clean_title(segments[-1]),
                    "title": _clean_title(" - ".join(segments[:-1])),
                }
            elif len(segments) >= 2:
                result = {
                    "author": _clean_title(segments[0]),
                    "title": _clean_title(" - ".join(segments[1:])),
                }
            else:
                result = {"author": "", "title": _clean_title(segments[0])}
        else:
            # A 3-way split where no series segment was found: check whether
            # the middle or trailing segment is noise (an edition/contributor
            # note, or a bare identifier) rather than real title/author
            # content, before falling back to the naive first-dash split
            # (which would otherwise merge that noise into the title/author
            # text -- e.g. "The Mask Falling - Author's preferred text -
            # Samantha Shannon" naively splitting into author="The Mask
            # Falling", title="Author's preferred text Samantha Shannon").
            noisy_idx = None
            if len(segments) == 3:
                candidates = [i for i in (1, 2) if _is_noise_segment(segments[i])]
                if len(candidates) == 1:
                    noisy_idx = candidates[0]

            if noisy_idx is not None:
                remaining = [segments[i] for i in range(3) if i != noisy_idx]
                left = _clean_title(remaining[0])
                right = _clean_title(remaining[1])
            else:
                parts = cleaned.split(" - ", 1)
                left = _clean_title(parts[0])
                right = _clean_title(parts[1])
            result = _assign_author_title(left, right)

        result["series"] = series
        result["series_seq"] = series_seq
        return result

    # Check for "Title by Author" pattern (e.g. "The Burning God by R. F. Kuang")
    by_match = re.search(r"\s+by\s+", cleaned, re.IGNORECASE)
    if by_match:
        left = _clean_title(cleaned[:by_match.start()])
        right = _clean_title(cleaned[by_match.end():])
        # Only treat "by" as separator when left is a plausible title (2+ words)
        # and right is a plausible author name (1-4 words)
        if len(left.split()) >= 2 and 1 <= len(right.split()) <= 4:
            return {"author": right, "title": left, "series": series, "series_seq": series_seq}

    return {"author": "", "title": _clean_title(cleaned), "series": series, "series_seq": series_seq}


def parse_comic_name(name: str) -> dict:
    """
    Best-effort extraction of series name and volume/chapter/issue number
    from a comic or manga filename (e.g. "One Piece v03 (Digital)", "Batman
    - Hush #001", "Attack on Titan Vol. 5 [Kodansha]").

    Comics/manga are organized by series rather than a unique book title, and
    releases rarely carry an author in the filename, so unlike
    parse_torrent_name this doesn't attempt an author/title split.
    """
    name = _LEADING_TRACK_RE.sub("", name).strip()
    cleaned = _BRACKET_RE.sub(" ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    seq = ""
    matches = [m for m in (_VOLUME_RE.search(cleaned), _CHAPTER_RE.search(cleaned), _ISSUE_RE.search(cleaned)) if m]
    if matches:
        earliest = min(matches, key=lambda m: m.start())
        seq = earliest.group(1)
        cleaned = cleaned[:earliest.start()]

    return {"author": "", "title": _clean_title(cleaned), "series_seq": seq}


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

def _title_score(parsed_title: str, candidate_title: str, containment_boost: bool = True) -> float:
    """
    Blend token_sort_ratio and token_set_ratio.
    token_set_ratio handles the case where the parsed title contains the real
    title plus subtitle noise from the filename.  We dampen it when the
    candidate is much shorter than the parsed title to avoid false positives
    from short candidates matching by coincidence.

    containment_boost: set False by callers that can't also verify the
    author (see _score's `whole_title` caller in _resolve_from_parsed) --
    full title-word containment alone isn't a safe enough signal without
    that second check (verified real false positive: a "The Beast" by
    Jenika Snow download matching R.L. Stine's unrelated same-titled "The
    Beast" at 0.925 once the boost applied with no author check backing it
    up; author-similarity string metrics can't reliably tell that apart
    from a legitimate pen name like Katherine Addison/Sarah Monette, whose
    similarity score lands right next to the wrong-book case's).
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

    length_ratio = min(a_words, b_words) / max(a_words, b_words)

    # set_s == 1.0 means every word of the shorter title appears verbatim in
    # the longer one -- the mismatch is pure appended/prepended noise (a
    # series descriptor, subtitle, or edition tag the filename or the API
    # added) rather than genuinely different content. That's a much
    # stronger signal than a partial word overlap, so barely dampen it.
    # Partial overlaps (set_s < 1.0) keep the harsher proportional dampening
    # to avoid false positives from short candidates matching by coincidence.
    if set_s == 1.0 and containment_boost:
        blended_set = 0.85 + 0.15 * length_ratio
    else:
        blended_set = set_s * (0.5 + 0.5 * length_ratio)
    return max(sort_s, blended_set)


def _score(candidate: dict, parsed: dict, containment_boost: bool = True) -> float:
    title_s = _title_score(parsed.get("title", ""), candidate.get("title", ""), containment_boost=containment_boost)
    author = parsed.get("author", "")

    # When no author was parsed from the filename, use 100% title weight.
    # Penalizing for a missing author would unfairly hurt well-tagged title-only files.
    if not author:
        return title_s

    # token_set_ratio (not token_sort_ratio) so a parsed single author isn't
    # penalized against a candidate's multi-credit author field (co-authors,
    # translators, "Joe Hill - introduction"-style contributor credits) --
    # token_sort_ratio scores "Stephen King" vs "Stephen King, Joe Hill -
    # introduction" at only 52% despite it being a correct match.
    author_s = fuzz.token_set_ratio(
        candidate.get("author", ""), author
    ) / 100
    return title_s * 0.65 + author_s * 0.35


# --- Search + score helpers ---

def _search_and_score(
    author: str, title: str, category: str, is_comic: bool = False, match_method: str = "primary",
    score_author: str | None = None,
) -> list:
    """Run the appropriate API search and return scored candidates, best first.

    match_method: provenance tag recording which resolve_metadata cascade
    branch produced this candidate list (e.g. "primary", "flipped",
    "subtitle_trimmed") -- carried through to the UI for debugging.

    score_author: when set, scores candidates against this author instead of
    `author` -- used by the title_only retry, which deliberately searches
    with an empty author (to sidestep combined-query parser issues) but must
    NOT also score with an empty author. `_score` gives 100% weight to title
    when the scored author is empty (a well-tagged title-only *filename*
    shouldn't be penalized for the absence), which is correct for a filename
    that genuinely has no author -- but here the author was dropped only for
    the query, not because we don't know it, so scoring blind let a
    completely different book with the same title win with a perfect 1.0
    (verified real false positives: "The Beast" by Jenika Snow matched to
    "The Beast" by R.L. Stine; "The Hunter" by Jenika Snow matched to "The
    Hunter" by Julia Leigh). Scoring against the real author restores the
    normal 65/35 title/author blend and penalizes exactly these cases."""
    query = f"{author} {title}".strip()
    parsed = {"author": author if score_author is None else score_author, "title": title}

    if category == "audiobook":
        candidates = _search_audible(query)
        if not candidates:
            candidates = _search_itunes(query)
        if not candidates:
            candidates = _search_googlebooks(query)
    elif is_comic:
        candidates = _search_comicvine(query)
        if not candidates:
            candidates = _search_anilist(query)
        if not candidates:
            candidates = _search_googlebooks(query)
    else:
        candidates = _search_openlibrary(query)
        if not candidates:
            candidates = _search_googlebooks(query)

    if not candidates:
        return []

    return sorted(
        [{"score": _score(c, parsed), "match_method": match_method, **c} for c in candidates],
        key=lambda x: x["score"],
        reverse=True,
    )


# --- Metadata API clients ---

def audible_product_to_candidate(product: dict) -> dict:
    """Map a raw Audible catalog product to our candidate dict shape.
    Shared between _search_audible and app.matching.resolution's by-ASIN
    lookup, which hits a different endpoint but gets the same product shape
    back."""
    authors = [a["name"] for a in product.get("authors", []) if a.get("name")]
    series_list = product.get("series", [])
    series = series_list[0].get("title", "") if series_list else ""
    series_seq = series_list[0].get("sequence", "") if series_list else ""
    return {
        "title": product.get("title", ""),
        "author": ", ".join(authors),
        "series": series,
        "series_seq": series_seq,
        "source": "audible",
        "raw": product,
    }


# Audible's unofficial catalog API has no documented SLA and rate-limits
# aggressively under back-to-back requests (observed live: a retry
# re-querying the same title ~10s after the first request succeeded still
# got a 429). Retry a
# bounded number of times with backoff rather than immediately falling
# through to iTunes/Google Books, which lack series data and can drop a
# confident match below CONFIDENCE_THRESHOLD.
_AUDIBLE_MAX_ATTEMPTS = 3
_AUDIBLE_RETRY_BACKOFF_SECONDS = 1


def _search_audible(query: str) -> list:
    for attempt in range(_AUDIBLE_MAX_ATTEMPTS):
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
            return [audible_product_to_candidate(p) for p in data.get("products", [])[:5]]
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            retryable = status == 429 or (status is not None and status >= 500)
            if retryable and attempt < _AUDIBLE_MAX_ATTEMPTS - 1:
                retry_after = e.response.headers.get("Retry-After") if e.response is not None else None
                delay = float(retry_after) if retry_after else _AUDIBLE_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                time.sleep(delay)
                continue
            current_app.logger.warning(f"Audible search failed: {e}")
            return []
        except requests.exceptions.RequestException as e:
            if attempt < _AUDIBLE_MAX_ATTEMPTS - 1:
                time.sleep(_AUDIBLE_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                continue
            current_app.logger.warning(f"Audible search failed: {e}")
            return []
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


def _pick_isbn(isbns: list) -> str:
    """OpenLibrary's docs[].isbn is a list of mixed ISBN-10/ISBN-13 strings
    with no ordering guarantee -- prefer ISBN-13."""
    for i in isbns:
        if len(i) == 13:
            return i
    for i in isbns:
        if len(i) == 10:
            return i
    return ""


def _search_openlibrary(query: str) -> list:
    try:
        resp = requests.get(
            "https://openlibrary.org/search.json",
            # OpenLibrary's own relevance ranking buries the canonical edition
            # of popular books under study guides, summaries, and translations
            # (e.g. "The Alchemist" itself doesn't appear until position 9-11).
            # Fetch a wider pool and let our own fuzzy scoring pick the best one.
            params={"q": _sanitize_query(query), "limit": 20},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for doc in data.get("docs", [])[:20]:
            results.append({
                "title": doc.get("title", ""),
                "author": ", ".join(doc.get("author_name", [])),
                "series": "",
                "series_seq": "",
                "isbn": _pick_isbn(doc.get("isbn", [])),
                "source": "openlibrary",
                "raw": doc,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"OpenLibrary search failed: {e}")
        return []


def _search_comicvine(query: str) -> list:
    """Search ComicVine for western comic volumes/series. Skipped if no API key configured."""
    api_key = current_app.config.get("COMICVINE_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://comicvine.gamespot.com/api/search/",
            params={
                "api_key": api_key,
                "format": "json",
                "query": query,
                "resources": "volume",
                "limit": 10,
            },
            headers={"User-Agent": "annex"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", [])[:10]:
            series_title = item.get("name", "")
            publisher = (item.get("publisher") or {}).get("name", "")
            results.append({
                "title": series_title,
                "author": publisher,
                "series": series_title,
                "series_seq": "",
                "source": "comicvine",
                "raw": item,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"ComicVine search failed: {e}")
        return []


def _search_anilist(query: str) -> list:
    """Search AniList for manga series. No API key required."""
    graphql_query = """
    query ($search: String) {
        Page(perPage: 10) {
            media(search: $search, type: MANGA) {
                title { romaji english }
                staff(perPage: 3) { nodes { name { full } } }
            }
        }
    }
    """
    try:
        resp = requests.post(
            "https://graphql.anilist.co",
            json={"query": graphql_query, "variables": {"search": query}},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        media = data.get("data", {}).get("Page", {}).get("media", []) or []
        results = []
        for item in media[:10]:
            title_obj = item.get("title") or {}
            series_title = title_obj.get("english") or title_obj.get("romaji", "")
            staff_nodes = (item.get("staff") or {}).get("nodes", [])
            author = ", ".join(
                n["name"]["full"] for n in staff_nodes if n.get("name", {}).get("full")
            )
            results.append({
                "title": series_title,
                "author": author,
                "series": series_title,
                "series_seq": "",
                "source": "anilist",
                "raw": item,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"AniList manga search failed: {e}")
        return []


def _pick_google_isbn(identifiers: list) -> str:
    """Google Books' volumeInfo.industryIdentifiers is a list of
    {type, identifier} objects -- prefer ISBN_13 over ISBN_10."""
    by_type = {i.get("type"): i.get("identifier", "") for i in identifiers}
    return by_type.get("ISBN_13") or by_type.get("ISBN_10") or ""


def _search_googlebooks(query: str) -> list:
    try:
        resp = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": 20},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("items", [])[:20]:
            info = item.get("volumeInfo", {})
            results.append({
                "title": info.get("title", ""),
                "author": ", ".join(info.get("authors", [])),
                "series": "",
                "series_seq": "",
                "isbn": _pick_google_isbn(info.get("industryIdentifiers", [])),
                "source": "googlebooks",
                "raw": info,
            })
        return results
    except Exception as e:
        current_app.logger.warning(f"Google Books search failed: {e}")
        return []


def resolve_metadata(
    torrent_name: str, category: str, hint_author: str = "", is_comic: bool = False
) -> dict:
    """
    Returns:
        {
            "confidence": float,
            "match": {title, author, series, series_seq} or None,
            "candidates": [top 3 with scores]
        }

    hint_author: author string read from file tags — used when none can be
                 parsed from the filename itself.
    is_comic: True for comic/manga archive formats. Uses series/volume-aware
              filename parsing and searches ComicVine/AniList instead of
              OpenLibrary/Google Books.
    """
    parsed = parse_comic_name(torrent_name) if is_comic else parse_torrent_name(torrent_name)

    # Use file-tag author only when the filename gave us nothing
    if hint_author and not parsed["author"]:
        parsed["author"] = hint_author.strip()

    return _resolve_from_parsed(parsed, category, is_comic)


def _resolve_from_parsed(parsed: dict, category: str, is_comic: bool) -> dict:
    """The actual search/score/filter cascade, split out from resolve_metadata
    so app.matching.orchestrator's resolve_metadata_v2 can reuse it
    with a dict from extraction.extract() instead of parse_torrent_name --
    same keys (author, title, series, series_seq), extra isbn/asin keys are
    simply ignored here same as today."""
    threshold = current_app.config["CONFIDENCE_THRESHOLD"]

    scored = _search_and_score(
        parsed["author"], parsed["title"], category, is_comic=is_comic, match_method="primary"
    )
    confident = bool(scored) and scored[0]["score"] >= threshold

    # The author/title-flip and subtitle-trim retries below assume prose
    # novel filenames (an "Author - Title" split, a colon-separated subtitle).
    # Comics/manga are parsed as a bare series name with no author, so neither
    # heuristic applies.
    if not is_comic:
        # When the filename had a clear Author - Title split, also try the reversed
        # interpretation (Title - Author) and take whichever direction scores higher.
        # This handles cases where the heuristic guessed wrong (e.g. equal word counts,
        # or a short title that looks like a name). Skipped once we already have a
        # confident match -- these extra API calls (and their fallback cascades)
        # add up across a large backlog and are wasted once we know the answer.
        if not confident and parsed["author"] and parsed["title"]:
            flipped = _search_and_score(parsed["title"], parsed["author"], category, match_method="flipped")
            if flipped and (not scored or flipped[0]["score"] > scored[0]["score"]):
                scored = flipped
            confident = bool(scored) and scored[0]["score"] >= threshold

        # Filenames often carry a subtitle after a colon or semicolon (e.g.
        # "Democracy Awakening; Notes on the State of America") that metadata
        # APIs frequently omit from the main title. That mismatch alone can tank
        # an otherwise-correct match's score. Try scoring against just the main
        # title too and keep whichever interpretation scores higher.
        main_title = re.split(r"[:;]", parsed["title"], maxsplit=1)[0].strip()
        if not confident and main_title and main_title != parsed["title"]:
            trimmed = _search_and_score(parsed["author"], main_title, category, match_method="subtitle_trimmed")
            if trimmed and (not scored or trimmed[0]["score"] > scored[0]["score"]):
                scored = trimmed
            confident = bool(scored) and scored[0]["score"] >= threshold

        # Every retry above still combines author and title into one query --
        # a source's query parser can fail on that combined term set for
        # reasons unrelated to whether the book exists at all (verified: an
        # apostrophe in the title breaking OpenLibrary's combined-term
        # matching, see _sanitize_query -- that's now handled at the source,
        # but this is a general backstop for whatever the next one turns out
        # to be). Only worth the extra API call when every attempt so far
        # came back completely empty, not just unconfident.
        #
        # score_author=parsed["author"] is load-bearing, not optional: search
        # with an empty author (to dodge combined-query breakage) but still
        # score against the real one, so a same-titled but wrong-author book
        # can't win with a false 1.0 (real false positives found live: "The
        # Beast" by Jenika Snow -> R.L. Stine's unrelated "The Beast"; "The
        # Hunter" by Jenika Snow -> Julia Leigh's unrelated "The Hunter").
        if not scored and parsed["title"]:
            title_only = _search_and_score(
                "", parsed["title"], category, match_method="title_only", score_author=parsed["author"]
            )
            if title_only:
                scored = title_only
                confident = bool(scored) and scored[0]["score"] >= threshold

        # A clean "A - B" split doesn't always mean B is an author -- e.g.
        # translated works are often named "English Title - Native Title"
        # with no author anywhere in the filename. Re-score the same
        # candidates (no new API call -- same query text either way) as a
        # single title-only string and keep whichever interpretation scores
        # higher, so a wrong author guess can't tank an otherwise-correct
        # title match.
        if not confident and parsed["author"] and scored:
            whole_title = f"{parsed['author']} {parsed['title']}".strip()
            as_whole = sorted(
                [
                    # containment_boost=False: this branch's scoring deliberately
                    # blanks the author (below) so a coincidentally
                    # title-matching book by a completely different author can
                    # still win -- that's the point of this branch (real filenames
                    # like "English Title - Native Title" have no author anywhere
                    # to check against). Combining that with the containment boost
                    # is what caused a real false positive (see _title_score's
                    # docstring), so this call site alone opts out of it.
                    # An author-similarity veto was tried here and reverted: it
                    # broke this branch's own legitimate no-real-author case
                    # (verified: a real pen name pair and a real wrong-author pair
                    # scored 0.33 vs 0.31 -- indistinguishable noise, not a usable
                    # signal). containment_boost=False alone keeps both known false
                    # positives (the Stine/Snow "Beast" case and the Sweterlitsch/
                    # Zevin "Tomorrow" case) safely under threshold without it.
                    {
                        **c,
                        "score": _score(c, {"author": "", "title": whole_title}, containment_boost=False),
                        "match_method": "whole_title",
                    }
                    for c in scored
                ],
                key=lambda x: x["score"],
                reverse=True,
            )
            if as_whole and as_whole[0]["score"] > scored[0]["score"]:
                scored = as_whole

    if not scored:
        return {"confidence": 0.0, "match": None, "candidates": []}

    # Hard-disqualify summary-mill matches and series_seq conflicts BEFORE the
    # fill-in blocks below, which would otherwise paper over a real candidate/
    # filename disagreement by borrowing the filename's own series_seq value.
    scored = scoring.filter_candidates(scored, parsed)
    if not scored:
        return {"confidence": 0.0, "match": None, "candidates": []}

    # ComicVine/AniList return the series name but not a volume/chapter/issue
    # number -- that only lives in the filename, so carry it over here.
    if is_comic and parsed.get("series_seq"):
        for c in scored:
            c["series"] = c.get("series") or c.get("title", "")
            c["series_seq"] = parsed["series_seq"]

    # Prose/audiobook APIs (OpenLibrary, Google Books) don't return series
    # data at all, and Audible only sometimes does -- fall back to whatever
    # the filename itself told us (e.g. "Zodiac Academy 07 - Heartless Sky").
    if not is_comic and (parsed.get("series") or parsed.get("series_seq")):
        for c in scored:
            c["series"] = c.get("series") or parsed.get("series", "")
            c["series_seq"] = c.get("series_seq") or parsed.get("series_seq", "")

    top = scored[0]

    return {
        "confidence": top["score"],
        "match": top if top["score"] >= threshold else None,
        "candidates": scored[:3],
    }
