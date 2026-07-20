from app.matching import orchestrator, resolution


def test_v2_exact_isbn_short_circuits_fuzzy_cascade(app, http_mock):
    http_mock.on_get("openlibrary.org/api/books", {
        "ISBN:9780061122415": {
            "title": "The Alchemist",
            "authors": [{"name": "Paulo Coelho"}],
        }
    })

    result = orchestrator.resolve_metadata_v2(
        "The Alchemist - Paulo Coelho [9780061122415]", "ebook"
    )

    assert result["confidence"] == 1.0
    assert result["match"]["title"] == "The Alchemist"
    assert result["match"]["match_method"] == "exact_id"
    # The fuzzy cascade (title/author search) must never run once an exact
    # ID lookup succeeds.
    assert not http_mock.called("openlibrary.org/search.json")


def test_v2_falls_through_to_fuzzy_cascade_without_isbn_asin(app, http_mock):
    http_mock.on_get("openlibrary.org/search.json", {
        "docs": [{"title": "Dune", "author_name": ["Frank Herbert"]}]
    })

    result = orchestrator.resolve_metadata_v2("Dune - Frank Herbert", "ebook")

    assert result["match"] is not None
    assert result["match"]["title"] == "Dune"
    assert result["match"]["source"] == "openlibrary"


def test_v2_falls_through_when_isbn_lookup_misses(app, http_mock):
    # ISBN present in the filename, but neither exact-ID source has it --
    # must fall through to the normal fuzzy search/score cascade rather
    # than returning no match.
    http_mock.on_get("openlibrary.org/api/books", {})
    http_mock.on_get("googleapis.com/books", {"items": []})
    http_mock.on_get("openlibrary.org/search.json", {
        "docs": [{"title": "Dune", "author_name": ["Frank Herbert"]}]
    })

    result = orchestrator.resolve_metadata_v2(
        "Dune - Frank Herbert [9780061122415]", "ebook"
    )

    assert result["match"] is not None
    assert result["match"]["title"] == "Dune"
    assert result["match"]["match_method"] != "exact_id"


def test_v2_asin_lookup_skipped_for_ebook_category(app, http_mock, monkeypatch):
    # resolution.resolve already gates ASIN lookups to audiobook only
    # (Phase 2) -- confirm the orchestrator doesn't bypass that gate.
    called = []
    monkeypatch.setattr(
        resolution, "resolve_by_asin", lambda asin: called.append(asin) or None
    )
    http_mock.on_get("openlibrary.org/search.json", {
        "docs": [{"title": "Some Book", "author_name": ["Some Author"]}]
    })

    orchestrator.resolve_metadata_v2("Some Book - Some Author [B0D6PCZ98M]", "ebook")

    assert called == []
