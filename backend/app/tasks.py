import json
import logging
import time
from pathlib import Path

from flask import current_app

from app import celery, db
from app.models import Import
from app.abs import ABSClient
from app.metadata import resolve_metadata
from app.fileops import discover_files, build_target_dir, hardlink_files

logger = logging.getLogger(__name__)

# Minimum seconds since last modification before a path is considered stable
FILE_STABILITY_SECONDS = 60


def _is_stable(path: Path) -> bool:
    """Returns True if the path hasn't been modified recently."""
    try:
        mtime = path.stat().st_mtime
        return (time.time() - mtime) >= FILE_STABILITY_SECONDS
    except OSError:
        return False


@celery.task(name="app.tasks.scan_watch_dirs")
def scan_watch_dirs():
    watch_dirs = {
        "audiobook": current_app.config.get("AUDIOBOOK_WATCH_PATH", ""),
        "ebook": current_app.config.get("EBOOK_WATCH_PATH", ""),
    }

    for category, watch_path in watch_dirs.items():
        if not watch_path:
            continue

        root = Path(watch_path)
        if not root.is_dir():
            logger.warning(f"Watch path does not exist: {watch_path}")
            continue

        extensions = (
            current_app.config["AUDIOBOOK_EXTENSIONS"]
            if category == "audiobook"
            else current_app.config["EBOOK_EXTENSIONS"]
        )

        # Collect top-level entries that contain matching files
        candidates = set()
        for item in root.iterdir():
            if item.is_file() and item.suffix.lower() in extensions:
                candidates.add(item)
            elif item.is_dir():
                if any(f.suffix.lower() in extensions for f in item.rglob("*") if f.is_file()):
                    candidates.add(item)

        for path in candidates:
            existing = Import.query.filter_by(content_path=str(path)).first()
            if existing:
                continue

            if not _is_stable(path):
                logger.debug(f"Skipping unstable path: {path}")
                continue

            record = Import(
                hash=None,
                name=path.name,
                category=category,
                content_path=str(path),
                status="pending",
            )
            db.session.add(record)
            db.session.commit()

            import_item.delay(record.id)


@celery.task(name="app.tasks.import_item")
def import_item(import_id: int):
    record = Import.query.get(import_id)
    if not record:
        return

    record.status = "importing"
    db.session.commit()

    try:
        _run_import(record)
    except Exception as e:
        logger.exception(f"Import {import_id} failed: {e}")
        record.status = "failed"
        record.error_message = str(e)
        db.session.commit()


def _run_import(record: Import):
    files = discover_files(record.content_path, record.category)
    if not files:
        raise ValueError(f"No matching files found in {record.content_path}")

    result = resolve_metadata(record.name, record.category)
    record.metadata_confidence = result["confidence"]
    record.candidates_json = json.dumps([
        {k: v for k, v in c.items() if k != "raw"}
        for c in result["candidates"]
    ])

    if result["match"] is None:
        record.status = "needs_review"
        db.session.commit()
        return

    _finalize_import(record, result["match"], files)


def _finalize_import(record: Import, match: dict, files: list[Path]):
    record.resolved_author = match["author"]
    record.resolved_title = match["title"]
    record.resolved_series = match.get("series", "")
    record.resolved_series_seq = match.get("series_seq", "")

    target_dir = build_target_dir(
        category=record.category,
        author=match["author"],
        title=match["title"],
        series=match.get("series", ""),
        series_seq=match.get("series_seq", ""),
    )

    hardlink_files(files, target_dir, match["title"])
    record.target_path = str(target_dir)
    record.status = "imported"
    db.session.commit()

    try:
        ABSClient().scan_library(record.category)
    except Exception as e:
        logger.warning(f"ABS scan failed (import still succeeded): {e}")
