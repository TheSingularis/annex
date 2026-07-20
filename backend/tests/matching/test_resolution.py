from app.matching import resolution


# --- resolve_by_isbn ---

def test_resolve_by_isbn_via_openlibrary(app, http_mock):
    http_mock.on_get("openlibrary.org/api/books", {
        "ISBN:9780061122415": {
            "title": "The Alchemist",
            "authors": [{"name": "Paulo Coelho"}],
        }
    })
    result = resolution.resolve_by_isbn("9780061122415")
    assert result["title"] == "The Alchemist"
    assert result["author"] == "Paulo Coelho"
    assert result["isbn"] == "9780061122415"
    assert result["source"] == "openlibrary"


def test_resolve_by_isbn_falls_back_to_googlebooks(app, http_mock):
    # OpenLibrary's response omits the requested ISBN key entirely --
    # simulates "we don't have this edition".
    http_mock.on_get("openlibrary.org/api/books", {})
    http_mock.on_get("googleapis.com/books", {
        "items": [{"volumeInfo": {"title": "The Alchemist", "authors": ["Paulo Coelho"]}}]
    })
    result = resolution.resolve_by_isbn("9780061122415")
    assert result["title"] == "The Alchemist"
    assert result["source"] == "googlebooks"


def test_resolve_by_isbn_none_when_neither_source_has_it(app, http_mock):
    http_mock.on_get("openlibrary.org/api/books", {})
    http_mock.on_get("googleapis.com/books", {"items": []})
    assert resolution.resolve_by_isbn("9780061122415") is None


# --- resolve_by_asin ---

def test_resolve_by_asin_real_audible_product(app, http_mock):
    http_mock.on_get("api.audible.com/1.0/catalog/products/B08G9PRS1K", {
        "product": {
            "asin": "B08G9PRS1K",
            "title": "Project Hail Mary",
            "authors": [{"name": "Andy Weir", "asin": "B00G0WYW92"}],
            "series": [],
        }
    })
    result = resolution.resolve_by_asin("B08G9PRS1K")
    assert result["title"] == "Project Hail Mary"
    assert result["author"] == "Andy Weir"
    assert result["asin"] == "B08G9PRS1K"
    assert result["source"] == "audible"


def test_resolve_by_asin_none_for_sparse_non_audiobook_asin(app, http_mock):
    # The real shape Audible returns for an ASIN it doesn't carry as a
    # product -- e.g. a general Amazon.com catalog ASIN pulled from an
    # ebook filename rather than an Audible-specific product ID.
    http_mock.on_get("api.audible.com/1.0/catalog/products/B0D6PCZ98M", {
        "product": {"asin": "B0D6PCZ98M", "asset_details": [], "is_vvab": False}
    })
    assert resolution.resolve_by_asin("B0D6PCZ98M") is None


# --- resolve() priority + category gate ---

def test_resolve_prefers_isbn_over_asin(app, http_mock):
    http_mock.on_get("openlibrary.org/api/books", {
        "ISBN:9780061122415": {"title": "The Alchemist", "authors": [{"name": "Paulo Coelho"}]}
    })
    result = resolution.resolve("9780061122415", "B08G9PRS1K", "audiobook")
    assert result["source"] == "openlibrary"
    assert not http_mock.called("api.audible.com")


def test_resolve_falls_back_to_asin_when_no_isbn(app, http_mock):
    http_mock.on_get("api.audible.com/1.0/catalog/products/B08G9PRS1K", {
        "product": {"title": "Project Hail Mary", "authors": [{"name": "Andy Weir"}], "series": []}
    })
    result = resolution.resolve(None, "B08G9PRS1K", "audiobook")
    assert result["source"] == "audible"


def test_resolve_skips_asin_lookup_for_ebooks(app, http_mock):
    # Even with an ASIN present, ebooks never hit Audible's catalog -- it
    # only has real data for products it sells as audiobooks.
    result = resolution.resolve(None, "B0D6PCZ98M", "ebook")
    assert result is None
    assert not http_mock.called("api.audible.com")


def test_resolve_none_when_nothing_available(app, http_mock):
    assert resolution.resolve(None, None, "ebook") is None
