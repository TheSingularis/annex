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


# --- is_unwanted_collection_candidate ---

@pytest.mark.parametrize("title", [
    "Pittacus Lore Box Set",
    "The Wayward Pines 3-in-1 Collection",
    "Cixin Liu Bestselling Collecting Books Series, Set of 4 Books",
    "Throne Of Glass Series Collection 5 Books Set By Sarah J. Maas",
    "Mickey7 Series, 2 Books Set",
])
def test_is_unwanted_collection_candidate_title_pattern(title):
    candidate = {"title": title}
    assert scoring.is_unwanted_collection_candidate(candidate, {"title": "Death's End"})


def test_is_unwanted_collection_candidate_not_flagged_when_filename_is_actually_a_collection():
    # The download genuinely is a compilation -- don't disqualify the
    # matching compilation candidate in that case.
    candidate = {"title": "Jim Butcher's the Dresden Files Collection"}
    parsed = {"title": "The Dresden Files 1-15 + Side Jobs Collection"}
    assert not scoring.is_unwanted_collection_candidate(candidate, parsed)


def test_is_unwanted_collection_candidate_real_single_book_not_flagged():
    candidate = {"title": "Dark Rise"}
    assert not scoring.is_unwanted_collection_candidate(candidate, {"title": "Dark Rise"})


def test_is_unwanted_collection_candidate_slash_joined_series_listing():
    # Real false positive: a single "Throne of Glass" book 1 download
    # matched a candidate whose title is the entire 8-book series
    # slash-joined -- no "collection"/"box set" wording, just structure.
    candidate = {
        "title": "The Assassin's Blade / Throne of Glass / Crown of Midnight / "
                  "Heir of Fire / Queen of Shadows / Empire of Storms / Tower of Dawn / Kingdom of Ash"
    }
    assert scoring.is_unwanted_collection_candidate(candidate, {"title": "Throne of Glass"})


# --- is_derivative_work_candidate ---

@pytest.mark.parametrize("title", [
    "Witcher Series TRIVIA QUIZ BOOK",
    "The Real Life of Anthony Burgess",
    "Atomic Habits Quiz Questions",
])
def test_is_derivative_work_candidate_title_pattern(title):
    candidate = {"title": title}
    assert scoring.is_derivative_work_candidate(candidate, {"title": "Something Else"})


def test_is_derivative_work_candidate_does_not_flag_life_of_pi():
    # "life of" alone (without "real") is too broad -- would false-positive
    # on real titles like "Life of Pi".
    candidate = {"title": "Life of Pi"}
    assert not scoring.is_derivative_work_candidate(candidate, {"title": "Life of Pi"})


def test_is_derivative_work_candidate_real_book_not_flagged():
    candidate = {"title": "Witcher Series"}
    assert not scoring.is_derivative_work_candidate(candidate, {"title": "Witcher Series"})


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
