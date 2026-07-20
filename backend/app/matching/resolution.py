"""
Exact-ID resolution: given an ISBN or ASIN already extracted from a filename
or embedded metadata, look up the book directly instead of falling back to
fuzzy title/author search.

Not wired into the live app yet -- app/metadata.py's resolve_metadata still
does the actual resolving. See /root/.claude/plans/jolly-greeting-karp.md
(Phase 2).
"""
import requests
from flask import current_app

from app.metadata import audible_product_to_candidate


def _openlibrary_books_api(isbn: str) -> dict | None:
    """Single-call lookup with author names included directly (unlike the
    /isbn/{isbn}.json edition endpoint, which only returns an author *key*
    reference and would need a second request to resolve)."""
    try:
        resp = requests.get(
            "https://openlibrary.org/api/books",
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        book = data.get(f"ISBN:{isbn}")
        if not book:
            return None
        authors = [a.get("name", "") for a in book.get("authors", []) if a.get("name")]
        return {
            "title": book.get("title", ""),
            "author": ", ".join(authors),
            "series": "",
            "series_seq": "",
            "isbn": isbn,
            "source": "openlibrary",
            "raw": book,
        }
    except Exception as e:
        current_app.logger.warning(f"OpenLibrary ISBN lookup failed: {e}")
        return None


def _googlebooks_isbn_query(isbn: str) -> dict | None:
    try:
        resp = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": f"isbn:{isbn}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None
        info = items[0].get("volumeInfo", {})
        return {
            "title": info.get("title", ""),
            "author": ", ".join(info.get("authors", [])),
            "series": "",
            "series_seq": "",
            "isbn": isbn,
            "source": "googlebooks",
            "raw": info,
        }
    except Exception as e:
        current_app.logger.warning(f"Google Books ISBN lookup failed: {e}")
        return None


def resolve_by_isbn(isbn: str) -> dict | None:
    """OpenLibrary's Books API first (single call, has author names
    directly), Google Books isbn: query as fallback."""
    result = _openlibrary_books_api(isbn)
    if result and result["title"]:
        return result
    return _googlebooks_isbn_query(isbn)


def _audible_by_asin(asin: str) -> dict | None:
    try:
        resp = requests.get(
            f"https://api.audible.com/1.0/catalog/products/{asin}",
            params={"response_groups": "contributors,product_desc,product_attrs,series"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        product = data.get("product", {})
        # A real Audible product returns a title; an ASIN Audible doesn't
        # carry (e.g. a general Amazon.com catalog ASIN pulled from an
        # ebook filename, not an Audible-specific product ID) comes back
        # as just {"asin": ..., "asset_details": [], "is_vvab": false} --
        # no title, no authors. Treat that as "not found", not a match.
        if not product.get("title"):
            return None
        candidate = audible_product_to_candidate(product)
        candidate["asin"] = asin
        return candidate
    except Exception as e:
        current_app.logger.warning(f"Audible ASIN lookup failed: {e}")
        return None


def resolve_by_asin(asin: str) -> dict | None:
    return _audible_by_asin(asin)


def resolve(isbn: str | None, asin: str | None, category: str) -> dict | None:
    """
    Priority entry point: ISBN-exact (any category) -> ASIN-exact
    (audiobook only -- an ASIN found in an ebook filename is unlikely to be
    an Audible product ID; Audible's catalog only has real data for
    products it actually sells as audiobooks) -> None (caller falls through
    to the existing structured/fuzzy search cascade).
    """
    if isbn:
        result = resolve_by_isbn(isbn)
        if result:
            return result

    if asin and category == "audiobook":
        result = resolve_by_asin(asin)
        if result:
            return result

    return None
