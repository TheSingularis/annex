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


def test_parse_torrent_name_strips_azw3_extension():
    # "azw3" was missing from the junk-word list, so it survived as a
    # trailing word and threw off the word-count author/title heuristic.
    result = metadata.parse_torrent_name("Dune - Frank Herbert.azw3")
    assert result["author"] == "Frank Herbert"
    assert result["title"] == "Dune"


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
def test_parse_torrent_name_series(name, expected):
    result = metadata.parse_torrent_name(name)
    assert result["author"] == expected["author"]
    assert result["title"] == expected["title"]
    assert result["series"] == expected["series"]
    assert result["series_seq"] == expected["series_seq"]


def test_parse_torrent_name_series_normalizes_fake_colon():
    # Release groups sometimes swap ':' for a lookalike unicode character to
    # dodge filesystem restrictions on real colons.
    result = metadata.parse_torrent_name("Heir of Fire꞉ Throne of Glass, Book 3.m4b")
    assert result["title"] == "Heir of Fire"
    assert result["series"] == "Throne of Glass"


def test_parse_torrent_name_accepts_underscore_as_colon_substitute():
    # Real example: "Moss'd in Space_  Moss'd in Space, Book 1.m4b" -- the
    # real title is "Moss'd in Space: Moss'd in Space, Book 1", but whatever
    # stripped the filesystem-illegal ':' substituted a plain '_' instead of
    # one of the unicode lookalikes the fake-colon case above already
    # handles.
    result = metadata.parse_torrent_name("Moss'd in Space_  Moss'd in Space, Book 1.m4b")
    assert result["title"] == "Moss'd in Space"
    assert result["series"] == "Moss'd in Space"
    assert result["series_seq"] == "1"


def test_parse_torrent_name_underscore_word_separator_still_works():
    # '_' is also a plain word-separator convention ("Author_-_Title") --
    # widening the colon-series regex to accept '_' must not break that,
    # since this filename has no ", Book N" tail for the colon-series regex
    # to latch onto in the first place.
    result = metadata.parse_torrent_name("Frank_Herbert_-_Dune.epub")
    assert result["author"] == "Frank Herbert"
    assert result["title"] == "Dune"


@pytest.mark.parametrize("name", [
    # A title with a number in it must not be misread as "series N" --
    # only a 3+ segment split (a real author segment present) is safe to
    # treat that way. Two segments is too ambiguous either direction.
    "Fahrenheit 451 - A Novel",
    "Room 101 - Orwell",
])
def test_parse_torrent_name_no_false_positive_series(name):
    result = metadata.parse_torrent_name(name)
    assert result["series"] == ""
    assert result["series_seq"] == ""


def test_parse_torrent_name_no_false_positive_series_title():
    # "Fahrenheit 451" itself must survive intact, not get read as
    # series "Fahrenheit" book 451.
    result = metadata.parse_torrent_name("Fahrenheit 451 - A Novel")
    assert result["title"] == "Fahrenheit 451"


# --- 3-segment noise/identifier dropping ---

@pytest.mark.parametrize("name,expected_author,expected_title", [
    # Real recurring release convention: "Title - Author's preferred text -
    # Author" -- the middle segment is an edition note, not content.
    ("The Mask Falling - Author's preferred text - Samantha Shannon.epub", "Samantha Shannon", "The Mask Falling"),
    ("The Mime Order - Author's preferred text - Samantha Shannon.epub", "Samantha Shannon", "The Mime Order"),
    # Trailing segment is a bare ISBN-shaped digit run -- must be dropped,
    # not merged into the title.
    ("William Gibson - The Peripheral - 9780698170704.epub", "William Gibson", "The Peripheral"),
])
def test_parse_torrent_name_drops_noise_segment(name, expected_author, expected_title):
    result = metadata.parse_torrent_name(name)
    assert result["author"] == expected_author
    assert result["title"] == expected_title


def test_parse_torrent_name_noise_check_does_not_fire_outside_3_segments():
    # A 4-segment filename containing a segment that *would* match the noise
    # patterns must be left alone -- scope is exactly 3 segments, no
    # regression risk for longer splits.
    result = metadata.parse_torrent_name("Author - Series 01 - Title - trans Someone.epub")
    # Unaffected either way: the series-segment check already consumes
    # "Series 01" here, so this exercises the series_from_segment branch,
    # not our new noise-drop check -- confirms the two don't interact badly.
    assert result["series"] == "Series"
    assert result["series_seq"] == "01"


def test_parse_torrent_name_noise_check_still_wrong_for_known_open_gaps():
    # Known, separately-logged limitations this fix doesn't address --
    # documents current behavior so a future change to these doesn't
    # silently regress without anyone noticing. See the matcher-rebuild
    # roadmap backlog for why these are open, not fixed here.
    #
    # Tie-break coin-flip (verified against the real corpus: flipping the
    # default isn't a real improvement either) -- author/title still swapped.
    result = metadata.parse_torrent_name("Roadside Picnic - Arkady Strugatsky - trans Bormashenko.epub")
    assert result["author"] == "Roadside Picnic"
    assert result["title"] == "Arkady Strugatsky"

    # Mononym-author bug in _assign_author_title's single-word special case
    # (pre-existing, not specific to the 3-segment problem).
    result = metadata.parse_torrent_name("Homer - The Odyssey - read by Ian McKellen")
    assert result["author"] == "The Odyssey"
    assert result["title"] == "Homer"


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


# --- hard disqualification: summary-mill matches, series_seq conflicts (Phase 3) ---
# Unit tests for app.matching.scoring live in tests/matching/test_scoring.py. These
# integration tests prove the wiring point in resolve_metadata actually intercepts a
# HIGH-scoring wrong candidate -- monkeypatching _search_and_score with a pre-scored,
# above-threshold candidate makes that deterministic rather than depending on fuzzy
# string scoring happening to land above CONFIDENCE_THRESHOLD, which real-world
# summary-mill/wrong-installment candidates don't always do on title/author alone.

def test_series_seq_conflict_disqualifies_high_scoring_candidate(app, monkeypatch):
    # Regression: "Zodiac Academy 06" filenames were matching Audible's
    # "Zodiac Academy 8" because series-name word overlap dominated the
    # score. Even a candidate that scores WELL above threshold must be
    # hard-disqualified if its own series_seq ("8") disagrees with the
    # filename's parsed series_seq ("06").
    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        return [{
            "score": 0.95, "match_method": match_method,
            "title": "Zodiac Academy 8", "author": "Caroline Peckham, Susanne Valenti",
            "series": "Zodiac Academy", "series_seq": "8", "source": "audible",
        }]

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    result = metadata.resolve_metadata(
        "Caroline Peckham, Susanne Valenti - Zodiac Academy 06 - Fated Throne", "audiobook"
    )

    assert result["match"] is None
    assert result["candidates"] == []


def test_summary_mill_title_pattern_disqualified_even_high_scoring(app, monkeypatch):
    # Regression: study-guide products titled "Summary of X" beat the real
    # book because the real title is a literal word-subset of theirs --
    # that means they can genuinely outscore the real book, not just tie.
    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        return [{
            "score": 0.97, "match_method": match_method,
            "title": "Summary of Atomic Habits by James Clear", "author": "Some Publisher",
            "series": "", "series_seq": "", "source": "openlibrary",
        }]

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    result = metadata.resolve_metadata("Atomic Habits - James Clear", "ebook")

    assert result["match"] is None
    assert result["candidates"] == []


def test_summary_mill_publisher_disqualified_multi_contributor_author(app, monkeypatch):
    # Author strings are comma-joined multi-contributor lists (e.g. "IRB
    # Media, LLC"), not exact matches to the blocklist entry -- must match
    # per comma-segment, not the whole string.
    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        return [{
            "score": 0.92, "match_method": match_method,
            "title": "Surrounded by Psychopaths", "author": "IRB Media, LLC",
            "series": "", "series_seq": "", "source": "openlibrary",
        }]

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    result = metadata.resolve_metadata("Surrounded by Psychopaths - Thomas Erikson", "ebook")

    assert result["match"] is None
    assert result["candidates"] == []


def test_filter_candidates_empty_result_does_not_crash(app, monkeypatch):
    # Direct coverage of the IndexError risk: filtering every candidate out
    # must fall through to the standard empty-result shape, not raise.
    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        return [
            {"score": 0.9, "match_method": match_method, "title": "Summary of X", "author": "Wizer", "series": "", "series_seq": "", "source": "openlibrary"},
            {"score": 0.88, "match_method": match_method, "title": "Study Guide to X", "author": "Bookhabits", "series": "", "series_seq": "", "source": "openlibrary"},
        ]

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    result = metadata.resolve_metadata("X - Some Author", "ebook")

    assert result == {"confidence": 0.0, "match": None, "candidates": []}


# --- ISBN surfaced from already-fetched provider responses (Phase 1.5) ---

def test_search_openlibrary_extracts_isbn(app, http_mock):
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "The Alchemist", "author_name": ["Paulo Coelho"],
                   "isbn": ["0061122416", "9780061122415"]}]
    })
    results = metadata._search_openlibrary("The Alchemist Paulo Coelho")
    assert results[0]["isbn"] == "9780061122415"


def test_search_openlibrary_no_isbn_present(app, http_mock):
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "The Alchemist", "author_name": ["Paulo Coelho"]}]
    })
    results = metadata._search_openlibrary("The Alchemist Paulo Coelho")
    assert results[0]["isbn"] == ""


# --- query sanitization (real bug: OpenLibrary returns zero results for a
# combined author+title query containing an apostrophe, even though the
# same book is found instantly by a title-only query or the same combined
# query with the apostrophe stripped) ---

def test_sanitize_query_strips_straight_and_curly_apostrophes():
    assert metadata._sanitize_query("Rebecca Thorne Moss'd in Space") == "Rebecca Thorne Mossd in Space"
    assert metadata._sanitize_query("Moss’d in Space") == "Mossd in Space"


def test_search_openlibrary_sends_sanitized_query(app, monkeypatch):
    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"docs": []}

    def fake_get(url, params=None, **kwargs):
        captured["q"] = params.get("q") if params else None
        return _FakeResp()

    monkeypatch.setattr(metadata.requests, "get", fake_get)

    metadata._search_openlibrary("Rebecca Thorne Moss'd in Space")

    assert captured["q"] == "Rebecca Thorne Mossd in Space"


def test_search_googlebooks_extracts_isbn(app, http_mock):
    http_mock.on_get("googleapis.com/books", {
        "items": [{"volumeInfo": {
            "title": "The Alchemist", "authors": ["Paulo Coelho"],
            "industryIdentifiers": [
                {"type": "ISBN_10", "identifier": "0061122416"},
                {"type": "ISBN_13", "identifier": "9780061122415"},
            ],
        }}]
    })
    results = metadata._search_googlebooks("The Alchemist Paulo Coelho")
    assert results[0]["isbn"] == "9780061122415"


def test_search_googlebooks_isbn10_fallback(app, http_mock):
    http_mock.on_get("googleapis.com/books", {
        "items": [{"volumeInfo": {
            "title": "The Alchemist", "authors": ["Paulo Coelho"],
            "industryIdentifiers": [{"type": "ISBN_10", "identifier": "0061122416"}],
        }}]
    })
    results = metadata._search_googlebooks("The Alchemist Paulo Coelho")
    assert results[0]["isbn"] == "0061122416"


# --- _search_audible: retry/backoff on rate limiting (real bug: the Phase
# 4a shadow resolver re-querying Audible ~10s after the real import's own
# query got a 429 where the first request had succeeded) ---

class _FakeAudibleResp:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise metadata.requests.exceptions.HTTPError(response=self)

    def json(self):
        return self._json


def test_search_audible_retries_on_429_then_succeeds(app, monkeypatch):
    responses = [
        _FakeAudibleResp(status_code=429, headers={"Retry-After": "0"}),
        _FakeAudibleResp(json_data={"products": [
            {"title": "Dune", "authors": [{"name": "Frank Herbert"}]}
        ]}),
    ]
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(metadata.requests, "get", fake_get)
    monkeypatch.setattr(metadata.time, "sleep", lambda s: None)

    results = metadata._search_audible("Dune Frank Herbert")

    assert len(calls) == 2
    assert results[0]["title"] == "Dune"


def test_search_audible_honors_retry_after_header(app, monkeypatch):
    responses = [
        _FakeAudibleResp(status_code=429, headers={"Retry-After": "7"}),
        _FakeAudibleResp(json_data={"products": []}),
    ]
    sleeps = []

    monkeypatch.setattr(metadata.requests, "get", lambda url, **k: responses.pop(0))
    monkeypatch.setattr(metadata.time, "sleep", lambda s: sleeps.append(s))

    metadata._search_audible("Dune Frank Herbert")

    assert sleeps == [7.0]


def test_search_audible_gives_up_after_max_attempts_on_persistent_429(app, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _FakeAudibleResp(status_code=429)

    monkeypatch.setattr(metadata.requests, "get", fake_get)
    monkeypatch.setattr(metadata.time, "sleep", lambda s: None)

    results = metadata._search_audible("Dune Frank Herbert")

    assert results == []
    assert len(calls) == metadata._AUDIBLE_MAX_ATTEMPTS


def test_search_audible_retries_on_connection_error(app, monkeypatch):
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise metadata.requests.exceptions.ConnectionError("boom")
        return _FakeAudibleResp(json_data={"products": []})

    monkeypatch.setattr(metadata.requests, "get", fake_get)
    monkeypatch.setattr(metadata.time, "sleep", lambda s: None)

    results = metadata._search_audible("Dune Frank Herbert")

    assert calls["n"] == 2
    assert results == []


def test_search_audible_does_not_retry_non_retryable_http_error(app, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _FakeAudibleResp(status_code=404)

    monkeypatch.setattr(metadata.requests, "get", fake_get)
    monkeypatch.setattr(metadata.time, "sleep", lambda s: None)

    results = metadata._search_audible("Dune Frank Herbert")

    assert results == []
    assert len(calls) == 1


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

    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
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
    assert result["match"]["match_method"] == "whole_title"


def test_resolve_metadata_fills_series_from_filename(app, http_mock):
    # OpenLibrary/Google Books don't return series data at all -- when the
    # filename itself named a series/number ("Zodiac Academy 07"), that
    # should end up on the final match rather than being lost.
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "Heartless Sky", "author_name": ["Caroline Peckham", "Susanne Valenti"]}]
    })

    result = metadata.resolve_metadata(
        "Caroline Peckham, Susanne Valenti - Zodiac Academy 07 - Heartless Sky", "ebook"
    )

    assert result["match"] is not None
    assert result["match"]["series"] == "Zodiac Academy"
    assert result["match"]["series_seq"] == "07"


def test_prose_low_confidence_retries_flip_and_subtitle_trim(app, monkeypatch):
    calls = []

    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        calls.append((author, title, score_author))
        return []

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    # " - " split gives a non-empty author and title, and the colon gives a
    # trimmable main_title -- both retry branches should fire when unconfident,
    # plus the title_only fallback since every attempt here comes back empty.
    result = metadata.resolve_metadata("Some Title: A Subtitle - Some Author", "ebook")

    assert result["match"] is None
    assert len(calls) == 4
    assert calls[3] == ("", "Some Title: A Subtitle", "Some Author")


def test_title_only_retry_finds_a_match_when_combined_query_finds_nothing(app, monkeypatch):
    # Simulates the real bug class this retry backstops: every combined
    # author+title query (primary, flipped, subtitle-trimmed) comes back
    # completely empty, but a title-only query would have found the book.
    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        if author == "" and title == "Moss'd in Space":
            return [{"score": 0.95, "match_method": match_method, "title": "Moss'd in Space",
                      "author": "Rebecca Thorne", "series": "", "series_seq": "", "source": "itunes"}]
        return []

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    result = metadata.resolve_metadata("Moss'd in Space - Rebecca Thorne", "ebook")

    assert result["match"] is not None
    assert result["match"]["match_method"] == "title_only"
    assert result["match"]["author"] == "Rebecca Thorne"


def test_title_only_retry_passes_real_author_as_score_author(app, monkeypatch):
    # Wiring regression for a real false positive found live: the title_only
    # retry must score candidates against the real parsed author, not the
    # blanked one used for the query, or a same-titled but wrong-author book
    # can win with a false-confident score ("The Beast" by Jenika Snow
    # matched to "The Beast" by Robert Lawrence Stine).
    captured = {}

    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        if match_method == "title_only":
            captured["author"] = author
            captured["score_author"] = score_author
            return []
        return []

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    metadata.resolve_metadata("The Beast by Jenika Snow", "ebook")

    assert captured["author"] == ""
    assert captured["score_author"] == "Jenika Snow"


def test_title_only_retry_scoring_penalizes_wrong_author_candidate(app, http_mock):
    # Same regression, exercised through the real _search_and_score/_score
    # code path (not faked) -- an unrelated same-titled book must not score
    # a false-confident match once score_author restores the normal
    # 65/35 title/author blend.
    http_mock.on_get("openlibrary.org", {
        "docs": [{"title": "The Beast", "author_name": ["Robert Lawrence Stine"]}]
    })

    result = metadata._search_and_score(
        "", "The Beast", "ebook", match_method="title_only", score_author="Jenika Snow"
    )

    assert result[0]["score"] < app.config["CONFIDENCE_THRESHOLD"]


def test_title_only_retry_skipped_when_primary_already_has_candidates(app, monkeypatch):
    # Must not fire (and spend an extra API call) once there's anything to
    # work with -- only a fully empty result set should trigger it.
    calls = []

    def fake_search_and_score(author, title, category, is_comic=False, match_method="primary", score_author=None):
        calls.append((author, title))
        return [{"score": 0.3, "match_method": match_method, "title": "Something Else",
                  "author": "Someone Else", "series": "", "series_seq": "", "source": "openlibrary"}]

    monkeypatch.setattr(metadata, "_search_and_score", fake_search_and_score)

    metadata.resolve_metadata("Some Title - Some Author", "ebook")

    assert ("", "Some Title") not in calls
