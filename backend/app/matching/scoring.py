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
        kept.append(c)
    return kept
