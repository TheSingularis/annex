import pytest
from thefuzz import fuzz

from app import metadata


# --- parse_torrent_name (prose ebooks/audiobooks) ---

@pytest.mark.parametrize("name,expected", [
    ("Dune - Frank Herbert", {"author": "Frank Herbert", "title": "Dune"}),
    ("Project Hail Mary by Andy Weir", {"author": "Andy Weir", "title": "Project Hail Mary"}),
    ("01 For We Are Many", {"author": "", "title": "For We Are Many"}),
    # "Author_-_Title" is a common release-name convention -- the dash is
    # flanked by underscores rather than real spaces.
    ("Operation_Bounce_House_-_Matt_Dinniman.epub", {"author": "Matt Dinniman", "title": "Operation Bounce House"}),
])
def test_parse_torrent_name(name, expected):
    result = metadata.parse_torrent_name(name)
    assert result["author"] == expected["author"]
    assert result["title"] == expected["title"]


def test_parse_torrent_name_strips_commas():
    # Commas are pure punctuation noise for search purposes, but were
    # previously left in place, which can zero out strict search APIs.
    result = metadata.parse_torrent_name("Hoax_ Donald Trump, Fox News - Brian Stelter.epub")
    assert "," not in result["title"]


def test_parse_torrent_name_strips_bracketed_junk():
    # Periods are treated as punctuation separators (_PUNCT_RE), same as
    # dashes/underscores, so "R. F. Kuang" comes out space-joined.
    result = metadata.parse_torrent_name("The Burning God by R. F. Kuang [EPUB] (Retail)")
    assert result["author"] == "R F Kuang"
    assert result["title"] == "The Burning God"


# --- parse_comic_name (comics/manga) ---

@pytest.mark.parametrize("name,expected_title,expected_seq", [
    ("One Piece v03 (Digital) (release-group).cbz", "One Piece", "3"),
    ("Batman - Hush #001 (2003).cbr", "Batman Hush", "1"),
    ("Attack on Titan Vol. 5 [Kodansha].cbz", "Attack on Titan", "5"),
    ("Chainsaw Man - Chapter 12.cbz", "Chainsaw Man", "12"),
    ("Saga v01.cbr", "Saga", "1"),
    ("Berserk.cbz", "Berserk", ""),
])
def test_parse_comic_name(name, expected_title, expected_seq):
    result = metadata.parse_comic_name(name)
    assert result["title"] == expected_title
    assert result["series_seq"] == expected_seq
    assert result["author"] == ""


# --- scoring ---

def test_title_score_exact_match_is_perfect():
    assert metadata._title_score("Dune", "Dune") == pytest.approx(1.0)


def test_title_score_boosted_by_set_ratio_for_subtitle_noise():
    # A long filename subtitle the API's canonical title omits shouldn't tank
    # the score the way plain token_sort_ratio alone would.
    candidate, parsed = "The Alchemist", "The Alchemist A Fable About Following Your Dream"
    score = metadata._title_score(candidate, parsed)
    plain_sort_ratio = fuzz.token_sort_ratio(candidate, parsed) / 100
    assert score > plain_sort_ratio


def test_score_ignores_author_when_none_parsed():
    candidate = {"title": "Dune", "author": "Someone Else Entirely"}
    parsed = {"title": "Dune", "author": ""}
    assert metadata._score(candidate, parsed) == pytest.approx(metadata._title_score("Dune", "Dune"))


def test_score_does_not_penalize_extra_author_credits():
    # Regression: token_sort_ratio scores this pair ~52% despite it being a
    # correct match, because it penalizes the extra "Joe Hill" contributor
    # credit. token_set_ratio (used for author scoring) should not.
    candidate = {"title": "It", "author": "Stephen King, Joe Hill - introduction"}
    parsed = {"title": "It", "author": "Stephen King"}
    assert metadata._score(candidate, parsed) >= 0.85


# --- resolve_metadata: source cascades (mocked HTTP) ---

def test_audiobook_cascade_stops_at_first_nonempty_source(app, http_mock):
    http_mock.on_get("api.audible.com", {"products": []})
    http_mock.on_get("itunes.apple.com", {
        "results": [{"trackName": "Project Hail Mary", "artistName": "Andy Weir"}]
    })

    result = metadata.resolve_metadata("Project Hail Mary by Andy Weir", "audiobook")

    assert result["match"]["source"] == "itunes"
    assert http_mock.called("api.audible.com")
    assert http_mock.called("itunes.apple.com")
    assert not http_mock.called("googleapis.com/books")


def test_ebook_cascade_uses_openlibrary_before_googlebooks(app, http_mock):
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "Dune", "author_name": ["Frank Herbert"]}]
    })

    result = metadata.resolve_metadata("Dune - Frank Herbert", "ebook")

    assert result["match"]["source"] == "openlibrary"
    assert not http_mock.called("googleapis.com/books")


def test_comic_without_api_key_skips_comicvine_and_uses_anilist(app, http_mock):
    app.config["COMICVINE_API_KEY"] = ""
    http_mock.on_post("graphql.anilist.co", {
        "data": {"Page": {"media": [{
            "title": {"romaji": "One Piece", "english": "One Piece"},
            "staff": {"nodes": [{"name": {"full": "Eiichiro Oda"}}]},
        }]}}
    })

    result = metadata.resolve_metadata(
        "One Piece v03 (Digital) (release-group).cbz", "ebook", is_comic=True
    )

    match = result["match"]
    assert match is not None
    assert match["source"] == "anilist"
    assert match["series"] == "One Piece"
    assert match["series_seq"] == "3"
    assert match["author"] == "Eiichiro Oda"
    assert not http_mock.called("comicvine.gamespot.com")


def test_comic_with_api_key_uses_comicvine_and_skips_anilist(app, http_mock):
    app.config["COMICVINE_API_KEY"] = "test-key-123"
    http_mock.on_get("comicvine.gamespot.com", {
        "results": [{"name": "Batman Hush", "publisher": {"name": "DC Comics"}}]
    })

    result = metadata.resolve_metadata("Batman - Hush #001.cbr", "ebook", is_comic=True)

    match = result["match"]
    assert match is not None
    assert match["source"] == "comicvine"
    assert match["series"] == "Batman Hush"
    assert match["series_seq"] == "1"
    assert match["author"] == "DC Comics"
    assert http_mock.called("comicvine.gamespot.com")
    assert not http_mock.called("graphql.anilist.co")


def test_below_threshold_yields_no_match_but_keeps_candidates(app, http_mock):
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "Something Else Entirely", "author_name": ["Random Person"]}]
    })

    result = metadata.resolve_metadata("Some Obscure Thing", "ebook")

    assert result["match"] is None
    assert result["confidence"] < app.config["CONFIDENCE_THRESHOLD"]
    assert len(result["candidates"]) > 0


# --- resolve_metadata: retry-heuristic branching ---

def test_comic_low_confidence_only_searches_once(app, monkeypatch):
    calls = []

    def fake_search_and_score(author, title, category, is_comic=False):
        calls.append((author, title, is_comic))
        return []

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    result = metadata.resolve_metadata(
        "Some Random Comic Name.cbz", "ebook", hint_author="Some Author", is_comic=True
    )

    assert result["match"] is None
    assert len(calls) == 1


def test_prose_low_confidence_retries_whole_title_when_split_guess_is_wrong(app, http_mock):
    # "English Title - Native Title" (e.g. translated works) has no author
    # anywhere in the filename, but the "A - B" split heuristic still
    # guesses one side is an author. The wrong author guess must not tank
    # an otherwise-correct title-only match.
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "Heaven Official's Blessing -- Tian Guan Ci Fu Vol. 2", "author_name": ["Mo Xiang Tong Xiu"]}]
    })

    result = metadata.resolve_metadata("Heaven Officials Blessing - Tian Guan Ci Fu Vol.2", "ebook")

    assert result["match"] is not None
    assert result["match"]["author"] == "Mo Xiang Tong Xiu"


def test_prose_low_confidence_retries_flip_and_subtitle_trim(app, monkeypatch):
    calls = []

    def fake_search_and_score(author, title, category, is_comic=False):
        calls.append((author, title))
        return []

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    # " - " split gives a non-empty author and title, and the colon gives a
    # trimmable main_title -- both retry branches should fire when unconfident.
    result = metadata.resolve_metadata("Some Title: A Subtitle - Some Author", "ebook")

    assert result["match"] is None
    assert len(calls) == 3
