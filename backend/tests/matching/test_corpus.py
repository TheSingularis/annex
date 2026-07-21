"""
Regression corpus for the matcher rebuild (see /root/.claude/plans/jolly-greeting-karp.md).

Phase 0 scope: ship the fixture and a baseline accuracy check against the
*current* extraction logic (app.metadata.parse_torrent_name /
parse_comic_name), so later phases have a concrete "before" number to beat.
This intentionally does not exercise the new app/matching/* modules --
those don't exist yet (Phase 1+).
"""
import json
from pathlib import Path

import pytest

from app import metadata
from app.matching import extraction

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "corpus.json"

# Measured against this branch's app.metadata via
# test_current_extraction_baseline_accuracy below: 34/213 and 16/213 scored
# corpus entries respectively (bumped from 29/213 and 14/213 by the
# multi-segment noise/identifier-segment fix -- both app.metadata and
# app.matching.extraction got the identical fix, kept in sync, so this
# ratchets up rather than needing a gap). Exact fractions, not rounded
# decimals, so a byte-for-byte-identical port doesn't spuriously fail this
# gate. The new app.matching.extraction module (Phase 1) must meet or beat
# both.
BASELINE_TITLE_AUTHOR_RATE = 34 / 213
BASELINE_ALL_FIELDS_RATE = 16 / 213


def _load_corpus():
    data = json.loads(FIXTURE_PATH.read_text())
    return data["_meta"], data["entries"]


def test_corpus_fixture_shape():
    meta, entries = _load_corpus()
    assert len(entries) == meta["counts"]["total"]
    for e in entries:
        assert e["name"]
        assert e["category"] in ("ebook", "audiobook")
        assert e["resolution"] in (
            "auto_approved_top_candidate",
            "manual_override",
            "skipped_ambiguous",
            "known_false_positive_trap",
        )
        if e["resolution"] == "skipped_ambiguous":
            assert e["expected"] is None
        else:
            assert e["expected"] is not None
            for key in ("author", "title", "series", "series_seq"):
                assert key in e["expected"]


def _extract(entry):
    if entry["is_comic"]:
        return metadata.parse_comic_name(entry["name"])
    return metadata.parse_torrent_name(entry["name"])


def test_current_extraction_baseline_accuracy():
    """
    Not a pass/fail correctness check on individual entries -- the whole point
    of this corpus is that today's extraction gets plenty of these wrong
    (that's the motivation for the rebuild). This just measures where we
    stand today so Phase 1's replacement has a number to beat.
    """
    _, entries = _load_corpus()
    scored = [e for e in entries if e["expected"] is not None]

    exact_title_author = 0
    exact_all_fields = 0
    for e in scored:
        got = _extract(e)
        expected = e["expected"]
        title_author_match = (
            got.get("title", "") == expected["title"]
            and got.get("author", "") == expected["author"]
        )
        if title_author_match:
            exact_title_author += 1
        if title_author_match and (
            got.get("series", "") == expected["series"]
            and got.get("series_seq", "") == expected["series_seq"]
        ):
            exact_all_fields += 1

    title_author_rate = exact_title_author / len(scored)
    all_fields_rate = exact_all_fields / len(scored)

    print(
        f"\nBaseline (current parse_torrent_name/parse_comic_name) against "
        f"{len(scored)} scored corpus entries:\n"
        f"  title+author exact match: {exact_title_author}/{len(scored)} "
        f"({title_author_rate:.1%})\n"
        f"  title+author+series+seq exact match: {exact_all_fields}/{len(scored)} "
        f"({all_fields_rate:.1%})"
    )

    # Canary, not a target: today's extraction alone (no API resolution, no
    # scoring/blocklist/ISBN layer) is expected to get a meaningful minority
    # exactly right on raw string extraction -- most of today's corrections
    # came from fixing the *search candidate*, not the filename parse. If
    # this drops much further, something upstream broke; it isn't a bar
    # Phase 1 needs to clear on parsing alone.
    assert title_author_rate > 0.10


def _extract_new(entry):
    return extraction.extract(entry["name"], is_comic=entry["is_comic"])


def test_new_extraction_meets_or_beats_baseline():
    """
    Phase 1 gate: app.matching.extraction (the refactored, independently-
    testable extraction module) must match or beat the old app.metadata
    extraction's accuracy against the same corpus. Doesn't need to be
    perfect -- most corpus misses are search/scoring problems (Phase 2/3),
    not filename-parsing problems -- but it must not regress.
    """
    _, entries = _load_corpus()
    scored = [e for e in entries if e["expected"] is not None]

    exact_title_author = 0
    exact_all_fields = 0
    for e in scored:
        got = _extract_new(e)
        expected = e["expected"]
        title_author_match = (
            got.title == expected["title"] and got.author == expected["author"]
        )
        if title_author_match:
            exact_title_author += 1
        if title_author_match and (
            got.series == expected["series"] and got.series_seq == expected["series_seq"]
        ):
            exact_all_fields += 1

    title_author_rate = exact_title_author / len(scored)
    all_fields_rate = exact_all_fields / len(scored)

    print(
        f"\napp.matching.extraction against {len(scored)} scored corpus entries:\n"
        f"  title+author exact match: {exact_title_author}/{len(scored)} "
        f"({title_author_rate:.1%}) -- baseline {BASELINE_TITLE_AUTHOR_RATE:.1%}\n"
        f"  title+author+series+seq exact match: {exact_all_fields}/{len(scored)} "
        f"({all_fields_rate:.1%}) -- baseline {BASELINE_ALL_FIELDS_RATE:.1%}"
    )

    assert title_author_rate >= BASELINE_TITLE_AUTHOR_RATE
    assert all_fields_rate >= BASELINE_ALL_FIELDS_RATE
