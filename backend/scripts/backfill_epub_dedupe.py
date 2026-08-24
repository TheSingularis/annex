"""
One-off backfill: scans EBOOK_LIBRARY_PATH for already-imported folders that
contain more than one ebook-format file (the pre-fix behavior hardlinked
every discovered file), and collapses each down to a single canonical
EPUB, using the same selection/conversion rules as the live import pipeline
(app.ebook_convert).

Not a Celery task, not scheduled, not exposed via any API route --
intentionally a manual, run-it-yourself operation.

Usage (inside the running container):
    docker exec -it annex python -m scripts.backfill_epub_dedupe
    docker exec -it annex python -m scripts.backfill_epub_dedupe --apply
    docker exec -it annex python -m scripts.backfill_epub_dedupe --apply --limit 5

Dry-run (no --apply) is the default and makes no filesystem changes.
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from app import create_app
from app.ebook_convert import EbookConversionError, convert_to_epub, needs_conversion, select_ebook_source
from app.fileops import sanitize

_FORMAT_EXTENSIONS = {".epub", ".azw3", ".mobi"}


def find_candidate_folders(library_root: Path):
    """Yields (folder, files) for every folder directly containing more than
    one file whose extension is in _FORMAT_EXTENSIONS -- these are the
    folders where the pre-fix pipeline linked every format as siblings."""
    for folder in sorted(p for p in library_root.rglob("*") if p.is_dir()):
        files = sorted(
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in _FORMAT_EXTENSIONS
        )
        if len(files) > 1:
            yield folder, files


def process_folder(folder: Path, files: list[Path], dry_run: bool) -> dict:
    chosen, passthrough = select_ebook_source(files)
    if chosen is None:
        return {"folder": str(folder), "action": "skip-no-ebook-format"}

    siblings_to_remove = [f for f in files if f != chosen and f not in passthrough]

    if needs_conversion(chosen):
        if dry_run:
            return {
                "folder": str(folder), "action": "would-convert",
                "source": chosen.name, "would_remove": [f.name for f in siblings_to_remove],
            }
        try:
            with tempfile.TemporaryDirectory(prefix="annex-backfill-") as tmp:
                epub_path = convert_to_epub(chosen, Path(tmp))
                dest = folder / f"{sanitize(folder.name)}.epub"
                shutil.copy2(epub_path, dest)
        except EbookConversionError as e:
            return {"folder": str(folder), "action": "error", "error": str(e)}
        for f in siblings_to_remove:
            f.unlink()
        return {
            "folder": str(folder), "action": "converted",
            "result": dest.name, "removed": [f.name for f in siblings_to_remove],
        }

    # Native epub already exists -- just drop the losing siblings.
    if dry_run:
        return {
            "folder": str(folder), "action": "would-dedupe",
            "keep": chosen.name, "would_remove": [f.name for f in siblings_to_remove],
        }
    for f in siblings_to_remove:
        f.unlink()
    return {"folder": str(folder), "action": "deduped", "keep": chosen.name,
            "removed": [f.name for f in siblings_to_remove]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually modify files (default: dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N folders (for testing)")
    args = parser.parse_args()
    dry_run = not args.apply

    app = create_app()
    with app.app_context():
        from app.app_settings import load as load_settings
        s = load_settings()
        library_root = Path(s.get("ebook_library_path") or app.config["EBOOK_LIBRARY_PATH"])
        print(f"Scanning {library_root} (dry_run={dry_run})")

        count = 0
        errors = 0
        for folder, files in find_candidate_folders(library_root):
            if args.limit is not None and count >= args.limit:
                break
            result = process_folder(folder, files, dry_run)
            print(result)
            count += 1
            if result.get("action") == "error":
                errors += 1

        suffix = " (dry run -- nothing changed, re-run with --apply)" if dry_run else ""
        print(f"\nProcessed {count} folder(s), {errors} error(s).{suffix}")
        sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
