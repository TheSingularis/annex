import subprocess
from pathlib import Path

# Formats eligible to become "the" ebook when no native epub is present, in
# preference order. PDF is deliberately excluded here -- it never competes
# for the selected slot and is never converted (Calibre's PDF->EPUB output
# is unreliable for anything that isn't plain reflowable text).
_CONVERTIBLE_PREFERENCE = (".azw3", ".mobi")


class EbookConversionError(Exception):
    """Raised when ebook-convert fails or is unavailable. Callers must treat
    this as a hard failure, not fall back to linking the unconverted file --
    that would just reproduce the bug this module exists to fix."""


def select_ebook_source(files: list[Path]) -> tuple[Path | None, list[Path]]:
    """
    Given all files discovered for an ebook import, decide which single file
    should become the library's one ebook, and which other files should
    still be linked through untouched (PDFs, comics, etc).

    Returns (chosen, passthrough):
      - chosen: a native .epub if one exists, else the best .azw3/.mobi
        candidate to convert, else None if there's no ebook-shaped file at
        all (e.g. a comic-only import).
      - passthrough: every discovered file that isn't one of the
        epub/azw3/mobi candidates -- i.e. PDFs and comics pass through
        untouched. Losing epub/azw3/mobi siblings are dropped entirely (not
        included in passthrough), since only one ebook file should ever be
        linked into the library.
    """
    epubs = [f for f in files if f.suffix.lower() == ".epub"]
    azw3s = [f for f in files if f.suffix.lower() == ".azw3"]
    mobis = [f for f in files if f.suffix.lower() == ".mobi"]

    format_files = set(epubs) | set(azw3s) | set(mobis)
    passthrough = [f for f in files if f not in format_files]

    if epubs:
        chosen = epubs[0]
    elif azw3s:
        chosen = azw3s[0]
    elif mobis:
        chosen = mobis[0]
    else:
        chosen = None

    return chosen, passthrough


def needs_conversion(source: Path | None) -> bool:
    return source is not None and source.suffix.lower() in _CONVERTIBLE_PREFERENCE


def convert_to_epub(source: Path, workdir: Path) -> Path:
    """
    Converts source (.azw3/.mobi) to .epub via Calibre's ebook-convert CLI,
    writing the result into workdir. Caller owns workdir's lifetime (e.g. a
    tempfile.TemporaryDirectory) and must keep it alive until the result has
    been consumed (linked/copied elsewhere).
    """
    dest = workdir / f"{source.stem}.epub"
    try:
        result = subprocess.run(
            ["ebook-convert", str(source), str(dest)],
            capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError:
        raise EbookConversionError("ebook-convert binary not found (is Calibre installed?)")
    except subprocess.TimeoutExpired:
        raise EbookConversionError(f"ebook-convert timed out converting {source.name}")

    if result.returncode != 0 or not dest.exists():
        raise EbookConversionError(
            f"ebook-convert failed for {source.name} (exit {result.returncode}): "
            f"{result.stderr.strip()[-500:]}"
        )
    return dest
