import json
import logging
from pathlib import Path

from app import celery, db
from app.models import Import
from app.qbit import QBittorrentClient
from app.abs import ABSClient
from app.metadata import resolve_metadata
from app.fileops import discover_files, build_target_dir, hardlink_files

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.poll_qbittorrent")
def poll_qbittorrent():
    client = QBittorrentClient()
    try:
        torrents = client.get_completed_torrents(categories=("audiobook", "ebook"))
    except Exception as e:
        logger.error(f"qBittorrent poll failed: {e}")
        return

    for torrent in torrents:
        hash_ = torrent.get("hash")
        if not hash_:
            continue

        existing = Import.query.filter_by(hash=hash_).first()
        if existing:
            continue

        record = Import(
            hash=hash_,
            name=torrent.get("name", ""),
            category=torrent.get("category", "").lower(),
            content_path=torrent.get("content_path", ""),
            status="pending",
        )
        db.session.add(record)
        db.session.commit()

        import_torrent.delay(record.id)


@celery.task(name="app.tasks.import_torrent")
def import_torrent(import_id: int):
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
    # File discovery
    files = discover_files(record.content_path, record.category)
    if not files:
        raise ValueError(f"No matching files found in {record.content_path}")

    # Metadata resolution
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
