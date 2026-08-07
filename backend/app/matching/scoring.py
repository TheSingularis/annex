"""
Hard disqualification of candidates that fuzzy title/author scoring alone
lets through as false positives.

Wired directly into app/metadata.py's resolve_metadata -- unlike
app/matching/extraction.py, identifiers.py, and resolution.py (all still
standalone/unwired pending Phase 4), this phase intentionally changes live
behavior to fix two real bugs found in a live-triage session:
summary-mill matches ("Summary of X" by a study-guide imprint beating the
real book) and wrong-series-installment matches. See
/root/.claude/plans/jolly-greeting-karp.md (Phase 3).
"""
import re

from flask import current_app

# Prefix-anchored on purpose (the load-bearing generalizable signal), widened to catch
# a leading article and and/to/& variants. Supplemented, not replaced, by the publisher
# blocklist below for cases the pattern alone won't catch. Suffix-form wrapping (e.g.
# "X (Summary and Analysis)") isn't caught by a prefix anchor -- known gap, not fixed here.
_SUMMARY_TITLE_RE = re.compile(
    # \s (not \b) after the connector -- \b never matches between "&" and a
    # following space, since neither side is a word character.
    r"^(?:a\s+|the\s+)?(summary|analysis|study guide|workbook)\s+(of|and|to|&)\s",
    re.IGNORECASE,
)

# Curated from real false positives found in a live-triage session (2026-07-19). Expected
# to need extending over time -- disqualifications are logged (not just silently filtered)
# so gaps surface in production rather than staying invisible.
_BLOCKED_PUBLISHERS = {"irb media", "wizer", "bookhabits", "bn publishing"}

# Catches box sets/omnibuses/bundles beating the single book they contain
# (e.g. a "Pittacus Lore" download matching "Pittacus Lore Box Set", or a
# lone "Death's End" matching a "Set of 4 Books" bundle candidate). Not
# anchored to start/end since these markers show up anywhere in the title
# ("The Wayward Pines 3-in-1 Collection", "5 Books Set By Sarah J. Maas").
# Covers both "set of N books" and the reversed "N books set" ordering seen
# in real listings.
_COLLECTION_TITLE_RE = re.compile(
    r"\b(collection|box\s*set|boxed\s*set|omnibus|bundle|\d+[\s-]in[\s-]1"
    r"|set\s+of\s+\d+\s+books|\d+\s+books?\s+set)\b",
    re.IGNORECASE,
)


def is_unwanted_collection_candidate(candidate: dict, parsed: dict) -> bool:
    """True if the candidate looks like a box set/omnibus/bundle but the
    filename itself gave no indication the download actually is one --
    i.e. this is a single book matching the compilation that contains it,
    not someone's real box set download."""
    if not _COLLECTION_TITLE_RE.search(candidate.get("title", "")):
        return False
    return not _COLLECTION_TITLE_RE.search(parsed.get("title", ""))


# Derivative works ABOUT a book/author rather than the book itself --
# trivia/quiz-book cash-ins and biographies-of-the-author beating the real
# single-author novel they're piggybacking on (verified real false
# positives: a "Witcher Series" download matching a "Witcher Series TRIVIA
# QUIZ BOOK", and a lone "Burgess, Anthony" matching "The real life of
# Anthony Burgess", a biography by a different author entirely). "life of"
# requires "real" so it doesn't catch legitimate titles like "Life of Pi".
_DERIVATIVE_WORK_RE = re.compile(
    r"\b(trivia|quiz\s+book|quiz\s+questions|the\s+real\s+life\s+of|biography\s+of)\b",
    re.IGNORECASE,
)


def is_derivative_work_candidate(candidate: dict, parsed: dict) -> bool:
    """True if the candidate looks like trivia/quiz-book/biography content
    about a book or author rather than the work itself, and the filename
    gave no indication that's actually what was downloaded."""
    if not _DERIVATIVE_WORK_RE.search(candidate.get("title", "")):
        return False
    return not _DERIVATIVE_WORK_RE.search(parsed.get("title", ""))


def is_summary_mill_candidate(candidate: dict) -> bool:
    """True if this looks like a study-guide/summary-mill product rather
    than the real book. Author strings are comma-joined multi-contributor
    lists (e.g. "IRB Media, LLC" or "IRB Media, John Smith" from
    _search_openlibrary/_search_googlebooks), so blocklist matching checks
    each comma-segment rather than the whole string."""
    title = candidate.get("title", "")
    author_segments = [a.strip().lower() for a in candidate.get("author", "").split(",")]
    if _SUMMARY_TITLE_RE.match(title):
        return True
    return any(seg in _BLOCKED_PUBLISHERS for seg in author_segments)


def _normalize_seq(s: str) -> str:
    try:
        return str(float(s))
    except ValueError:
        return s


def series_seq_conflicts(parsed_seq: str, candidate_seq: str) -> bool:
    """Narrow numeric-mismatch check only -- doesn't validate series *name*
    agreement, just that when both sides carry a number, the numbers don't
    disagree. No-op when either side is empty (no signal): OpenLibrary,
    Google Books, ComicVine, and AniList candidates never populate
    series_seq on their own, so in practice this only ever fires for
    Audible-sourced prose candidates."""
    if not parsed_seq or not candidate_seq:
        return False
    return _normalize_seq(parsed_seq) != _normalize_seq(candidate_seq)


def filter_candidates(candidates: list, parsed: dict) -> list:
    """Hard disqualification -- may return an empty list if every candidate
    conflicts, which is intentional (better to fall through to needs_review
    with zero candidates than show a confirmed-wrong one). Caller MUST
    re-check emptiness before indexing into the result."""
    kept = []
    for c in candidates:
        if is_summary_mill_candidate(c):
            current_app.logger.info(
                f"Disqualified summary-mill candidate: {c.get('title')!r} / {c.get('author')!r}"
            )
            continue
        if series_seq_conflicts(parsed.get("series_seq", ""), c.get("series_seq", "")):
            current_app.logger.info(
                f"Disqualified series_seq conflict: candidate={c.get('series_seq')!r} "
                f"parsed={parsed.get('series_seq')!r} for {c.get('title')!r}"
            )
            continue
        if is_unwanted_collection_candidate(c, parsed):
            current_app.logger.info(
                f"Disqualified box set/omnibus candidate: {c.get('title')!r} for "
                f"unrelated single-book download {parsed.get('title')!r}"
            )
            continue
        if is_derivative_work_candidate(c, parsed):
            current_app.logger.info(
                f"Disqualified trivia/biography candidate: {c.get('title')!r} for "
                f"unrelated download {parsed.get('title')!r}"
            )
            continue
        kept.append(c)
    return kept
