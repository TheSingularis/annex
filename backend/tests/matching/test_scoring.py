import pytest

from app.matching import scoring


# --- is_summary_mill_candidate ---

@pytest.mark.parametrize("title", [
    "Summary of Atomic Habits by James Clear",
    "A Summary of Atomic Habits",
    "The Study Guide to Atomic Habits",
    "Analysis and Review of Atomic Habits",
    "Workbook & Study Guide to Atomic Habits",
])
def test_is_summary_mill_candidate_title_pattern(title):
    candidate = {"title": title, "author": "Some Publisher"}
    assert scoring.is_summary_mill_candidate(candidate)


def test_is_summary_mill_candidate_real_book_title_not_flagged():
    candidate = {"title": "Atomic Habits", "author": "James Clear"}
    assert not scoring.is_summary_mill_candidate(candidate)


@pytest.mark.parametrize("author", [
    "Irb Media",
    "IRB Media, LLC",
    "IRB Media, John Smith",
    "Wizer",
    "Bookhabits",
])
def test_is_summary_mill_candidate_blocked_publisher(author):
    candidate = {"title": "Some Ordinary-Looking Title", "author": author}
    assert scoring.is_summary_mill_candidate(candidate)


def test_is_summary_mill_candidate_real_author_not_flagged():
    candidate = {"title": "Some Book", "author": "James Clear"}
    assert not scoring.is_summary_mill_candidate(candidate)


# --- series_seq_conflicts ---

def test_series_seq_conflicts_true_for_different_numbers():
    assert scoring.series_seq_conflicts("06", "8")


def test_series_seq_conflicts_false_for_equivalent_numbers():
    # Leading zeros, float-vs-int shapes -- "06" and "6.0" are the same book.
    assert not scoring.series_seq_conflicts("06", "6")
    assert not scoring.series_seq_conflicts("6", "6.0")


def test_series_seq_conflicts_false_when_either_side_empty():
    assert not scoring.series_seq_conflicts("", "8")
    assert not scoring.series_seq_conflicts("6", "")
    assert not scoring.series_seq_conflicts("", "")


def test_series_seq_conflicts_non_numeric_fallback():
    # Non-numeric values (e.g. a comic special/annual) fall back to plain
    # string comparison rather than crashing on float().
    assert scoring.series_seq_conflicts("Annual", "6")
    assert not scoring.series_seq_conflicts("Annual", "Annual")


# --- filter_candidates ---

def test_filter_candidates_removes_summary_mill_and_conflicting_seq(app):
    candidates = [
        {"title": "Summary of X", "author": "Irb Media", "series_seq": ""},
        {"title": "X", "author": "Real Author", "series_seq": "8"},
        {"title": "X", "author": "Real Author", "series_seq": "6"},
    ]
    result = scoring.filter_candidates(candidates, {"series_seq": "6"})
    assert result == [{"title": "X", "author": "Real Author", "series_seq": "6"}]


def test_filter_candidates_can_return_empty_list(app):
    candidates = [{"title": "Summary of X", "author": "Wizer", "series_seq": ""}]
    assert scoring.filter_candidates(candidates, {"series_seq": ""}) == []


def test_filter_candidates_keeps_everything_when_nothing_disqualified(app):
    candidates = [{"title": "X", "author": "Real Author", "series_seq": ""}]
    assert scoring.filter_candidates(candidates, {"series_seq": "6"}) == candidates
