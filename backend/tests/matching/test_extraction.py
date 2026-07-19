"""
Ported verbatim from tests/test_metadata.py's parse_torrent_name/
parse_comic_name sections, against the new app.matching.extraction module.
Same names/groupings (prefixed test_extract_ instead of
test_parse_torrent_name_) so a diff against the old file makes the 1:1
porting obvious. Scoring and resolve_metadata cascade tests are NOT ported
here -- out of scope for Phase 1 (see the roadmap plan).
"""
import pytest

from app.matching import extraction


# --- extract_prose ---

@pytest.mark.parametrize("name,expected", [
    ("Dune - Frank Herbert", {"author": "Frank Herbert", "title": "Dune"}),
    ("Project Hail Mary by Andy Weir", {"author": "Andy Weir", "title": "Project Hail Mary"}),
    ("01 For We Are Many", {"author": "", "title": "For We Are Many"}),
    # "Author_-_Title" is a common release-name convention -- the dash is
    # flanked by underscores rather than real spaces.
    ("Operation_Bounce_House_-_Matt_Dinniman.epub", {"author": "Matt Dinniman", "title": "Operation Bounce House"}),
])
def test_extract_prose(name, expected):
    result = extraction.extract_prose(name)
    assert result.author == expected["author"]
    assert result.title == expected["title"]


def test_extract_prose_strips_commas():
    # Commas are pure punctuation noise for search purposes, but were
    # previously left in place, which can zero out strict search APIs.
    result = extraction.extract_prose("Hoax_ Donald Trump, Fox News - Brian Stelter.epub")
    assert "," not in result.title


def test_extract_prose_strips_bracketed_junk():
    # Periods are treated as punctuation separators (_PUNCT_RE), same as
    # dashes/underscores, so "R. F. Kuang" comes out space-joined.
    result = extraction.extract_prose("The Burning God by R. F. Kuang [EPUB] (Retail)")
    assert result.author == "R F Kuang"
    assert result.title == "The Burning God"


def test_extract_prose_strips_azw3_extension():
    # "azw3" was missing from the junk-word list, so it survived as a
    # trailing word and threw off the word-count author/title heuristic.
    result = extraction.extract_prose("Dune - Frank Herbert.azw3")
    assert result.author == "Frank Herbert"
    assert result.title == "Dune"


# --- series/number detection (prose) ---

@pytest.mark.parametrize("name,expected", [
    # "Author - Series NN - Title" release convention
    (
        "Laurie Gilmore - The Dream Harbor 02 - The Cinnamon Bun Book Store.epub",
        {"author": "Laurie Gilmore", "title": "The Cinnamon Bun Book Store",
         "series": "The Dream Harbor", "series_seq": "02"},
    ),
    (
        "Caroline Peckham, Susanne Valenti - Zodiac Academy 07 - Heartless Sky",
        {"author": "Caroline Peckham Susanne Valenti", "title": "Heartless Sky",
         "series": "Zodiac Academy", "series_seq": "07"},
    ),
    # "Title (Series, Book N)" bracketed aside
    (
        "Cixin Liu - Death's End (The Three-Body Problem, Book 3)",
        {"author": "Cixin Liu", "title": "Death's End",
         "series": "The Three-Body Problem", "series_seq": "3"},
    ),
    # "Title: Series, Book N" with no author (comes from file tags instead)
    (
        "Heir of Fire: Throne of Glass, Book 3.m4b",
        {"author": "", "title": "Heir of Fire",
         "series": "Throne of Glass", "series_seq": "3"},
    ),
    # "Series NN - Title - Author" -- the series-first ordering, as opposed
    # to the more common "Author - Series NN - Title".
    (
        "Dungeon Crawler Carl 03 - The Dungeon Anarchist's Cookbook - Matt Dinniman.epub",
        {"author": "Matt Dinniman", "title": "The Dungeon Anarchist's Cookbook",
         "series": "Dungeon Crawler Carl", "series_seq": "03"},
    ),
    # A bracketed series aside doesn't tell us author/title ordering (unlike
    # a whole dash segment matching "<series> <N>"), so the word-count
    # heuristic still decides between the two remaining segments.
    (
        "The Three-Body Problem (The Three-Body Trilogy, Book 1) - Cixin Liu.azw3",
        {"author": "Cixin Liu", "title": "The Three Body Problem",
         "series": "The Three-Body Trilogy", "series_seq": "1"},
    ),
])
def test_extract_prose_series(name, expected):
    result = extraction.extract_prose(name)
    assert result.author == expected["author"]
    assert result.title == expected["title"]
    assert result.series == expected["series"]
    assert result.series_seq == expected["series_seq"]


def test_extract_prose_series_normalizes_fake_colon():
    # Release groups sometimes swap ':' for a lookalike unicode character to
    # dodge filesystem restrictions on real colons.
    result = extraction.extract_prose("Heir of Fire꞉ Throne of Glass, Book 3.m4b")
    assert result.title == "Heir of Fire"
    assert result.series == "Throne of Glass"


@pytest.mark.parametrize("name", [
    # A title with a number in it must not be misread as "series N" --
    # only a 3+ segment split (a real author segment present) is safe to
    # treat that way. Two segments is too ambiguous either direction.
    "Fahrenheit 451 - A Novel",
    "Room 101 - Orwell",
])
def test_extract_prose_no_false_positive_series(name):
    result = extraction.extract_prose(name)
    assert result.series == ""
    assert result.series_seq == ""


def test_extract_prose_no_false_positive_series_title():
    # "Fahrenheit 451" itself must survive intact, not get read as
    # series "Fahrenheit" book 451.
    result = extraction.extract_prose("Fahrenheit 451 - A Novel")
    assert result.title == "Fahrenheit 451"


# --- extract_comic ---

@pytest.mark.parametrize("name,expected_title,expected_seq", [
    ("One Piece v03 (Digital) (release-group).cbz", "One Piece", "3"),
    ("Batman - Hush #001 (2003).cbr", "Batman Hush", "1"),
    ("Attack on Titan Vol. 5 [Kodansha].cbz", "Attack on Titan", "5"),
    ("Chainsaw Man - Chapter 12.cbz", "Chainsaw Man", "12"),
    ("Saga v01.cbr", "Saga", "1"),
    ("Berserk.cbz", "Berserk", ""),
])
def test_extract_comic(name, expected_title, expected_seq):
    result = extraction.extract_comic(name)
    assert result.title == expected_title
    assert result.series_seq == expected_seq
    assert result.author == ""


# --- extract() top-level entry point (identifier merging) ---

def test_extract_merges_isbn_when_present():
    result = extraction.extract(
        "Paulo Coelho - The Alchemist (10th Anniversary ed) - 9780061741241.epub"
    )
    assert result.isbn == "9780061741241"
    assert result.author == "Paulo Coelho"


def test_extract_no_isbn_leaves_field_none():
    result = extraction.extract("Dune - Frank Herbert")
    assert result.isbn is None
    assert result.asin is None


def test_extract_dispatches_to_comic_extraction():
    result = extraction.extract("One Piece v03 (Digital).cbz", is_comic=True)
    assert result.title == "One Piece"
    assert result.series_seq == "3"
