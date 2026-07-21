"""
Filename -> {author, title, series, series_seq, isbn, asin} extraction.

Refactor of app.metadata.parse_torrent_name / parse_comic_name into named,
independently-testable steps. Behavior is ported deliberately, not
reimagined -- see /root/.claude/plans/jolly-greeting-karp.md (Phase 1) for
why: this is a testability refactor, not a rewrite, and the current
functions encode a lot of hard-won edge-case handling.

Not wired into the live app yet. app/metadata.py is untouched and still
what actually runs (see the roadmap for the phased cutover plan).
"""
import re
from dataclasses import dataclass, replace

from app.matching import identifiers

# --- Filename cleaning patterns (ported verbatim from app/metadata.py) ---

_BRACKET_RE = re.compile(r"[\[\(][^\]\)]*[\]\)]")
_PUNCT_RE = re.compile(r"[,_\-\.]+")
_JUNK_RE = re.compile(
    r"\b(audiobook|ebook|epub|mobi|azw3?|pdf|m4b|mp3|flac|aac|retail|true|unabridged"
    r"|repack|proper|cbz|cbr|cb7|cbt|digital|scan|\d{4})\b",
    re.IGNORECASE,
)
_LEADING_TRACK_RE = re.compile(r"^\d{1,3}\s+")
_TRAILING_NOISE_RE = re.compile(
    r"\s*[\-:]?\s*\b(?:a\s+(?:novel|memoir|thriller|novella|story)"
    r"|(?:\d+\w*\s+)?anniversary(?:\s+edition)?)\s*$",
    re.IGNORECASE,
)

_COLON_SUBSTITUTES = "꞉："

_BOOK_MARKER_RE = re.compile(
    r"^(?P<series>.+?),?\s+book\s+(?P<seq>\d+(?:\.\d+)?)$", re.IGNORECASE
)
_SEGMENT_SERIES_RE = re.compile(r"^(?P<series>.+?)\s+(?P<seq>\d{1,3}(?:\.\d+)?)$")

# Segments that are noise, not title/author content, when they show up as the
# middle or trailing segment of an otherwise-unresolved 3-way dash split.
# Mirrors app.metadata's identical constants -- kept in sync deliberately so
# Phase 4a's shadow resolver (app.matching.orchestrator, which calls this
# module) doesn't disagree with the live resolver over this fix alone.
_CREDIT_MARKER_RE = re.compile(
    r"^(?:trans(?:lated\s+by)?|read\s+by|narrated\s+by)\s+.+$", re.IGNORECASE
)
_NOISE_PHRASE_RE = re.compile(
    r"^(?:author'?s\s+preferred\s+text|corrected|unabridged|abridged)$", re.IGNORECASE
)
_IDENTIFIER_SEGMENT_RE = re.compile(r"^\d{9,13}(?:\.[A-Za-z0-9]{2,4})?$")


def _is_noise_segment(segment: str) -> bool:
    segment = segment.strip()
    return bool(
        _CREDIT_MARKER_RE.match(segment)
        or _NOISE_PHRASE_RE.match(segment)
        or _IDENTIFIER_SEGMENT_RE.match(segment)
    )


_COLON_SERIES_RE = re.compile(
    r"^(?P<title>.+?):\s*(?P<series>.+?),?\s+book\s+(?P<seq>\d+(?:\.\d+)?)"
    r"(?:\.[A-Za-z0-9]{2,4})?\s*$",
    re.IGNORECASE,
)

_VOLUME_RE = re.compile(r"\bv(?:ol(?:ume)?)?\.?\s*0*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"\bch(?:apter)?\.?\s*0*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_ISSUE_RE = re.compile(r"#\s*0*(\d+(?:\.\d+)?)\b")


@dataclass
class ExtractedName:
    author: str = ""
    title: str = ""
    series: str = ""
    series_seq: str = ""
    isbn: str | None = None
    asin: str | None = None


def _clean(s: str) -> str:
    s = _JUNK_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clean_title(s: str) -> str:
    s = _clean(s)
    s = _TRAILING_NOISE_RE.sub("", s).strip()
    return s


def _normalize(name: str) -> str:
    """Leading track-number strip + fake-colon-substitute normalization."""
    name = _LEADING_TRACK_RE.sub("", name).strip()
    for ch in _COLON_SUBSTITUTES:
        name = name.replace(ch, ":")
    return name


def _match_colon_series(name: str) -> ExtractedName | None:
    """'Title: Series, Book N' -- Audible-style, no author in this convention."""
    m = _COLON_SERIES_RE.match(name)
    if not m:
        return None
    return ExtractedName(
        author="",
        title=_clean_title(m.group("title")),
        series=_clean(m.group("series")),
        series_seq=m.group("seq"),
    )


def _find_bracket_series(raw_name: str) -> tuple[str, str]:
    """
    Series/book info in a bracketed aside, e.g. "Death's End (The Three-Body
    Problem, Book 3)". Must run on the name BEFORE bracket-stripping --
    once brackets are stripped the content is gone.
    """
    for bracket in _BRACKET_RE.finditer(raw_name):
        inner = bracket.group(0)[1:-1].strip()
        m = _BOOK_MARKER_RE.match(inner)
        if m:
            return m.group("series").strip(), m.group("seq")
    return "", ""


def _strip_brackets_and_normalize(name: str) -> str:
    cleaned = _BRACKET_RE.sub(" ", name)
    # Underscores are a common word-separator convention in release names
    # ("Author_-_Title.epub").
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\s*--+\s*", " - ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _find_segment_series(segments: list[str]) -> tuple[str, str, bool, list[str]]:
    """
    Release convention: "Author - Series NN - Title", or the reverse
    "Series NN - Title - Author". A segment (other than the very last)
    matching "<name> <N>" names a series entry. Requires 3+ segments (a
    real author segment present) -- with only 2 segments this is too
    ambiguous to guess (e.g. "Fahrenheit 451 - A Novel" is a title with a
    number in it, not series "Fahrenheit" book 451).

    Returns (series, series_seq, was_at_start, remaining_segments). If no
    match, returns ("", "", False, segments unchanged).
    """
    if len(segments) < 3:
        return "", "", False, segments

    for i in range(len(segments) - 1):
        m = _SEGMENT_SERIES_RE.match(segments[i])
        if m:
            remaining = segments[:i] + segments[i + 1:]
            return m.group("series").strip(), m.group("seq"), i == 0, remaining

    return "", "", False, segments


def _assign_author_title(left: str, right: str) -> tuple[str, str]:
    """
    Heuristic: the shorter part (fewer words) is more likely the author
    name. Special case: a single-word part is more likely a title than an
    author. Returns (author, title).
    """
    lw = len(left.split()) if left else 0
    rw = len(right.split()) if right else 0

    if lw == 1 and rw > 1:
        return right, left
    if rw == 1 and lw > 1:
        return left, right
    if lw <= rw:
        return left, right
    return right, left


def _split_author_title(cleaned: str, series: str, series_seq: str) -> ExtractedName:
    """
    Dash-split OR by-split OR bare title -- mutually exclusive at the top
    level, matching the original function exactly (the "by" pattern only
    ever applies when there's no " - " in the name at all).
    """
    if " - " in cleaned:
        segments = [s.strip() for s in cleaned.split(" - ")]

        seg_series, seg_seq, series_at_start, remaining = (
            ("", "", False, segments) if series else _find_segment_series(segments)
        )
        if seg_series:
            series, series_seq = seg_series, seg_seq
            segments = remaining

        if seg_series:
            # The series segment carried the ambiguity; whatever's left
            # keeps its original relative order, so no re-run of the
            # word-count heuristic. "Series NN - Title - Author" leaves
            # [Title, Author]; "Author - Series NN - Title" leaves
            # [Author, ..., Title]. (A series found via the bracketed-aside
            # case carries no such positional info, so it still falls
            # through to the heuristic below.)
            if series_at_start and len(segments) >= 2:
                author = _clean_title(segments[-1])
                title = _clean_title(" - ".join(segments[:-1]))
            elif len(segments) >= 2:
                author = _clean_title(segments[0])
                title = _clean_title(" - ".join(segments[1:]))
            else:
                author, title = "", _clean_title(segments[0])
        else:
            # A 3-way split where no series segment was found: check whether
            # the middle or trailing segment is noise (an edition/contributor
            # note, or a bare identifier) rather than real title/author
            # content, before falling back to the naive first-dash split.
            noisy_idx = None
            if len(segments) == 3:
                candidates = [i for i in (1, 2) if _is_noise_segment(segments[i])]
                if len(candidates) == 1:
                    noisy_idx = candidates[0]

            if noisy_idx is not None:
                remaining_segs = [segments[i] for i in range(3) if i != noisy_idx]
                author, title = _assign_author_title(
                    _clean_title(remaining_segs[0]), _clean_title(remaining_segs[1])
                )
            else:
                parts = cleaned.split(" - ", 1)
                author, title = _assign_author_title(
                    _clean_title(parts[0]), _clean_title(parts[1])
                )

        return ExtractedName(author=author, title=title, series=series, series_seq=series_seq)

    by_match = re.search(r"\s+by\s+", cleaned, re.IGNORECASE)
    if by_match:
        left = _clean_title(cleaned[:by_match.start()])
        right = _clean_title(cleaned[by_match.end():])
        # Only treat "by" as separator when left is a plausible title (2+
        # words) and right is a plausible author name (1-4 words)
        if len(left.split()) >= 2 and 1 <= len(right.split()) <= 4:
            return ExtractedName(author=right, title=left, series=series, series_seq=series_seq)

    return ExtractedName(author="", title=_clean_title(cleaned), series=series, series_seq=series_seq)


def extract_prose(name: str) -> ExtractedName:
    """Best-effort extraction of author, title, and series/number from a
    filename or folder name (prose ebooks/audiobooks)."""
    normalized = _normalize(name)

    colon_result = _match_colon_series(normalized)
    if colon_result:
        return colon_result

    series, series_seq = _find_bracket_series(normalized)
    cleaned = _strip_brackets_and_normalize(normalized)

    return _split_author_title(cleaned, series, series_seq)


def _find_comic_seq(cleaned: str) -> tuple[str, str]:
    """Volume/chapter/issue number, e.g. "Vol. 3", "v03", "Chapter 12", "#7".
    Returns (seq, remaining_title_with_seq_stripped)."""
    matches = [
        m for m in (_VOLUME_RE.search(cleaned), _CHAPTER_RE.search(cleaned), _ISSUE_RE.search(cleaned))
        if m
    ]
    if not matches:
        return "", cleaned
    earliest = min(matches, key=lambda m: m.start())
    return earliest.group(1), cleaned[:earliest.start()]


def extract_comic(name: str) -> ExtractedName:
    """
    Best-effort extraction of series name and volume/chapter/issue number
    from a comic or manga filename (e.g. "One Piece v03 (Digital)", "Batman
    - Hush #001", "Attack on Titan Vol. 5 [Kodansha]").

    Comics/manga are organized by series rather than a unique book title,
    and releases rarely carry an author in the filename, so unlike
    extract_prose this doesn't attempt an author/title split.
    """
    cleaned = _LEADING_TRACK_RE.sub("", name).strip()
    cleaned = _BRACKET_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    seq, cleaned = _find_comic_seq(cleaned)

    return ExtractedName(author="", title=_clean_title(cleaned), series_seq=seq)


def extract(name: str, is_comic: bool = False) -> ExtractedName:
    """
    Top-level entry point. Merges filename-based author/title/series
    extraction with ISBN/ASIN identifier extraction. This is the one
    function later phases will call.
    """
    result = extract_comic(name) if is_comic else extract_prose(name)
    isbn = identifiers.find_isbn(name)
    asin = identifiers.find_asin(name)
    if isbn or asin:
        result = replace(result, isbn=isbn, asin=asin)
    return result
