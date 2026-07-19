"""
ISBN/ASIN extraction from filenames and embedded EPUB metadata.

Stdlib only (zipfile + xml.etree.ElementTree) -- no new dependency for the
EPUB reader. See /root/.claude/plans/jolly-greeting-karp.md (Phase 1).
"""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ISBN13_RE = re.compile(r"\b(97[89]\d{10})\b")
ISBN10_RE = re.compile(r"\b(\d{9}[\dXx])\b")

# Narrow on purpose: only the B0-prefixed ASIN subset is validated against
# real data (one example in the roadmap, zero in the corpus). Do not widen
# without new evidence -- a bare \b[A-Z0-9]{10}\b would match far more false
# positives (hashes, release-group tags) than it's worth.
_ASIN_LIKELY_RE = re.compile(r"\b(B0[A-Z0-9]{8})\b")

_CONTAINER_PATH = "META-INF/container.xml"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


def isbn13_checksum_valid(isbn: str) -> bool:
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn[:12]))
    return (10 - total % 10) % 10 == int(isbn[12])


def _isbn10_to_isbn13(isbn10: str) -> str | None:
    """Deterministic ISBN-10 -> ISBN-13 conversion (strip check digit,
    prepend 978, recompute checksum). Returns None if isbn10 isn't 10 chars
    with a valid trailing check digit shape."""
    digits = isbn10[:9]
    if not digits.isdigit():
        return None
    candidate = "978" + digits
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(candidate))
    check = (10 - total % 10) % 10
    isbn13 = candidate + str(check)
    return isbn13 if isbn13_checksum_valid(isbn13) else None


def find_isbn(name: str) -> str | None:
    """Find a checksum-valid ISBN-13 in a filename. A bare 13-digit run
    (e.g. a timestamp or hash) will rarely pass the checksum by chance, so
    this is a real filter, not decoration."""
    for match in ISBN13_RE.finditer(name):
        candidate = match.group(1)
        if isbn13_checksum_valid(candidate):
            return candidate
    return None


def find_asin(name: str) -> str | None:
    m = _ASIN_LIKELY_RE.search(name)
    return m.group(1) if m else None


def _find_opf_path(zf: zipfile.ZipFile) -> str | None:
    """Parse META-INF/container.xml to find the real OPF path -- never
    hardcode 'content.opf', producers vary."""
    try:
        container_bytes = zf.read(_CONTAINER_PATH)
    except KeyError:
        return None

    root = ET.fromstring(container_bytes)
    rootfile = root.find(f".//{{{_CONTAINER_NS}}}rootfile")
    if rootfile is None:
        return None
    return rootfile.get("full-path")


def _extract_isbn_from_opf(opf_bytes: bytes) -> str | None:
    root = ET.fromstring(opf_bytes)

    # Namespace-agnostic: OPF producers (Calibre, Sigil, publisher tools)
    # vary slightly in namespace URI/prefix, so match on local tag name
    # rather than a hardcoded qualified name.
    identifier_elements = [el for el in root.iter() if el.tag.split("}")[-1] == "identifier"]
    if not identifier_elements:
        return None

    opf_ns_scheme_attrs = [
        "scheme",
        "{http://www.idpf.org/2007/opf}scheme",
    ]

    def _scheme_is_isbn(el) -> bool:
        for attr in opf_ns_scheme_attrs:
            val = el.get(attr, "")
            if "isbn" in val.lower():
                return True
        return False

    # Prefer an element explicitly scheme-tagged as ISBN.
    for el in identifier_elements:
        if _scheme_is_isbn(el) and el.text:
            candidate = re.sub(r"[^0-9Xx]", "", el.text.replace("urn:isbn:", ""))
            if len(candidate) == 13 and isbn13_checksum_valid(candidate):
                return candidate
            if len(candidate) == 10:
                isbn13 = _isbn10_to_isbn13(candidate)
                if isbn13:
                    return isbn13

    # Else scan all identifier text for anything ISBN-13-shaped.
    for el in identifier_elements:
        if not el.text:
            continue
        text = el.text.replace("urn:isbn:", "")
        m = ISBN13_RE.search(text.replace("-", ""))
        if m and isbn13_checksum_valid(m.group(1)):
            return m.group(1)

    # Else fall back to an ISBN-10-shaped identifier, normalized to ISBN-13.
    for el in identifier_elements:
        if not el.text:
            continue
        text = re.sub(r"[^0-9Xx]", "", el.text)
        if len(text) == 10:
            isbn13 = _isbn10_to_isbn13(text)
            if isbn13:
                return isbn13

    return None


def read_epub_isbn(path: Path) -> str | None:
    """Read the embedded ISBN from an epub's OPF metadata. Fails soft
    (returns None) on any error -- many real epub files are malformed or
    have stripped metadata."""
    try:
        with zipfile.ZipFile(path) as zf:
            opf_path = _find_opf_path(zf)
            if not opf_path:
                return None
            try:
                opf_bytes = zf.read(opf_path)
            except KeyError:
                # container.xml pointed at a path that doesn't actually
                # exist in the archive -- happens with hand-edited epubs.
                return None
            return _extract_isbn_from_opf(opf_bytes)
    except Exception:
        return None
