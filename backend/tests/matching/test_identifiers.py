import io
import zipfile

import pytest

from app.matching import identifiers


# --- isbn13_checksum_valid ---

@pytest.mark.parametrize("isbn", [
    "9780061741241",  # The Alchemist, 10th anniversary ed -- real corpus example
    "9781785042188",  # Surrounded by Idiots -- real corpus example
    "9780698170704",  # The Peripheral -- real corpus example
])
def test_isbn13_checksum_valid_real_examples(isbn):
    assert identifiers.isbn13_checksum_valid(isbn)


def test_isbn13_checksum_invalid_corrupted_digit():
    valid = "9780061741241"
    corrupted = valid[:-1] + str((int(valid[-1]) + 1) % 10)
    assert not identifiers.isbn13_checksum_valid(corrupted)


def test_isbn13_checksum_invalid_wrong_length():
    assert not identifiers.isbn13_checksum_valid("97800617412")


def test_isbn13_checksum_invalid_non_digit():
    assert not identifiers.isbn13_checksum_valid("978006174124X")


# --- find_isbn ---

def test_find_isbn_in_filename():
    result = identifiers.find_isbn(
        "Paulo Coelho - The Alchemist (10th Anniversary ed) - 9780061741241.epub"
    )
    assert result == "9780061741241"


def test_find_isbn_rejects_checksum_invalid_digit_run():
    # A random 13-digit run starting with 978 that doesn't pass the
    # checksum must not be reported as an ISBN -- this is what makes the
    # checksum meaningful rather than decorative.
    result = identifiers.find_isbn("Some Release 9781234567890 Extra Tag")
    assert result is None


def test_find_isbn_none_when_absent():
    assert identifiers.find_isbn("Dune - Frank Herbert") is None


# --- find_asin ---

def test_find_asin_in_bracketed_filename():
    result = identifiers.find_asin("Sunrise on the Reaping [B0D6PCZ98M]")
    assert result == "B0D6PCZ98M"


def test_find_asin_none_when_absent():
    assert identifiers.find_asin("Dune - Frank Herbert") is None


def test_find_asin_does_not_catch_non_b0_prefixed_asins():
    # Documented limitation, not a bug: real ASINs don't all start with
    # "B0" (older/third-party-catalog items reuse other prefixes or even
    # ISBN-10 values). This regex only covers the B0-prefixed subset that's
    # actually been observed in this project's data. Widening it needs new
    # evidence, not guesswork -- see the roadmap plan's Phase 1 notes.
    hypothetical_non_b0_asin = "A1B2C3D4E5"
    assert identifiers.find_asin(f"Some Book [{hypothetical_non_b0_asin}]") is None


# --- read_epub_isbn ---

_CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

_OPF_WITH_ISBN_SCHEME = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="uuid_id" opf:scheme="uuid">urn:uuid:12345</dc:identifier>
    <dc:identifier opf:scheme="ISBN">9780061741241</dc:identifier>
  </metadata>
</package>"""

_OPF_NO_ISBN = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier>urn:uuid:only-a-uuid-here</dc:identifier>
  </metadata>
</package>"""

_OPF_WITH_ISBN10 = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier>0061122416</dc:identifier>
  </metadata>
</package>"""


def _build_epub(opf_path: str, opf_content: str, include_container=True, opf_at_path=True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if include_container:
            zf.writestr("META-INF/container.xml", _CONTAINER_XML.format(opf_path=opf_path))
        if opf_at_path:
            zf.writestr(opf_path, opf_content)
    return buf.getvalue()


def _write_temp_epub(tmp_path, filename: str, data: bytes):
    path = tmp_path / filename
    path.write_bytes(data)
    return path


def test_read_epub_isbn_well_formed(tmp_path):
    data = _build_epub("OEBPS/content.opf", _OPF_WITH_ISBN_SCHEME)
    path = _write_temp_epub(tmp_path, "book.epub", data)
    assert identifiers.read_epub_isbn(path) == "9780061741241"


def test_read_epub_isbn_non_default_opf_path(tmp_path):
    # The OPF path must come from container.xml, never be hardcoded.
    data = _build_epub("OPS/package.opf", _OPF_WITH_ISBN_SCHEME)
    path = _write_temp_epub(tmp_path, "book.epub", data)
    assert identifiers.read_epub_isbn(path) == "9780061741241"


def test_read_epub_isbn_missing_container_xml(tmp_path):
    data = _build_epub("OEBPS/content.opf", _OPF_WITH_ISBN_SCHEME, include_container=False)
    path = _write_temp_epub(tmp_path, "book.epub", data)
    assert identifiers.read_epub_isbn(path) is None


def test_read_epub_isbn_container_points_at_missing_opf(tmp_path):
    data = _build_epub("OEBPS/content.opf", _OPF_WITH_ISBN_SCHEME, opf_at_path=False)
    path = _write_temp_epub(tmp_path, "book.epub", data)
    assert identifiers.read_epub_isbn(path) is None


def test_read_epub_isbn_no_isbn_present(tmp_path):
    data = _build_epub("OEBPS/content.opf", _OPF_NO_ISBN)
    path = _write_temp_epub(tmp_path, "book.epub", data)
    assert identifiers.read_epub_isbn(path) is None


def test_read_epub_isbn_malformed_xml(tmp_path):
    data = _build_epub("OEBPS/content.opf", "<not><valid xml")
    path = _write_temp_epub(tmp_path, "book.epub", data)
    assert identifiers.read_epub_isbn(path) is None


def test_read_epub_isbn_not_a_zip(tmp_path):
    path = tmp_path / "not-a-zip.epub"
    path.write_bytes(b"this is not a zip file at all")
    assert identifiers.read_epub_isbn(path) is None


def test_read_epub_isbn10_normalizes_to_isbn13(tmp_path):
    # 0061122416 is a real ISBN-10 (The Alchemist) -- confirms conversion.
    data = _build_epub("OEBPS/content.opf", _OPF_WITH_ISBN10)
    path = _write_temp_epub(tmp_path, "book.epub", data)
    result = identifiers.read_epub_isbn(path)
    assert result is not None
    assert len(result) == 13
    assert identifiers.isbn13_checksum_valid(result)
