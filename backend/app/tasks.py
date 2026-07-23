import json
import logging
import time
from itertools import zip_longest
from pathlib import Path

from celery.signals import worker_ready
from flask import current_app

from app import celery, db
from app.models import Import, ShadowMatch
from app.abs import ABSClient
from app.metadata import resolve_metadata
from app.matching.orchestrator import resolve_metadata_v2
from app.fileops import discover_files, build_target_dir, hardlink_files, is_comic

logger = logging.getLogger(__name__)

# Minimum seconds since last modification before a path is considered stable
FILE_STABILITY_SECONDS = 60

# How long to wait before running the shadow-mode resolver, so its Audible
# request doesn't land immediately after the real import's own Audible call
# for the same title.
SHADOW_MATCH_DELAY_SECONDS = 30


def _is_stable(path: Path) -> bool:
    """Returns True if the path hasn't been modified recently."""
    try:
        mtime = path.stat().st_mtime
        return (time.time() - mtime) >= FILE_STABILITY_SECONDS
    except OSError:
        return False


def _strip_raw(candidate: dict | None) -> dict | None:
    if candidate is None:
        return None
    return {k: v for k, v in candidate.items() if k != "raw"}


def _matches_agree(old_match: dict | None, new_match: dict | None) -> bool:
    """Coarse title/author string comparison -- good enough for a human to
    skim disagreements during the shadow-mode observation window, not a
    precision metric."""
    if old_match is None and new_match is None:
        return True
    if old_match is None or new_match is None:
        return False
    return (
        old_match.get("title", "").strip().lower() == new_match.get("title", "").strip().lower()
        and old_match.get("author", "").strip().lower() == new_match.get("author", "").strip().lower()
    )


def _dispatch_interleaved(ids_by_category: dict):
    """
    Queue import tasks round-robin across categories instead of one whole
    category at a time, so a large backlog in one (e.g. audiobooks) can't
    starve the other (e.g. ebooks) behind it in the FIFO task queue.
    """
    for group in zip_longest(*ids_by_category.values()):
        for import_id in group:
            if import_id is not None:
                import_item.delay(import_id)


@celery.task(name="app.tasks.scan_watch_dirs")
def scan_watch_dirs():
    from app.app_settings import load as load_settings
    s = load_settings()
    watch_dirs = {
        "audiobook": s.get("audiobook_watch_path", ""),
        "ebook": s.get("ebook_watch_path", ""),
    }

    new_ids = {category: [] for category in watch_dirs}

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
            # flush (not commit) so we get the autoincremented id without
            # opening/closing a separate write transaction per file — scans
            # can find hundreds of files at once and per-row commits here
            # were contending with worker processes writing status updates.
            db.session.flush()
            new_ids[category].append(record.id)

    db.session.commit()
    _dispatch_interleaved(new_ids)


def _requeue_stalled_imports():
    """
    Re-dispatch any import stuck in 'pending' or 'importing' whose queued
    task no longer exists (e.g. the broker restarted and lost its queue, or
    a previous worker process died mid-task). Without this, such records
    would sit stuck forever since scan_watch_dirs only enqueues files it
    hasn't seen before.
    """
    records = (
        Import.query.filter(Import.status.in_(("pending", "importing")))
        .order_by(Import.id)
        .all()
    )
    if not records:
        return

    ids_by_category = {}
    for record in records:
        ids_by_category.setdefault(record.category, []).append(record.id)

    logger.info(f"Re-dispatching {len(records)} stalled import(s) on worker startup")
    _dispatch_interleaved(ids_by_category)


@worker_ready.connect
def _on_worker_ready(**kwargs):
    try:
        _requeue_stalled_imports()
    except Exception:
        logger.exception("Failed to re-dispatch stalled imports on worker startup")


@celery.task(name="app.tasks.import_item")
def import_item(import_id: int):
    record = Import.query.get(import_id)
    if not record:
        return

    try:
        record.status = "importing"
        db.session.commit()
        _run_import(record)
    except Exception as e:
        logger.exception(f"Import {import_id} failed: {e}")
        db.session.rollback()
        record = Import.query.get(import_id)
        if record:
            record.status = "failed"
            record.error_message = str(e)
            db.session.commit()


def _run_import(record: Import):
    files = discover_files(record.content_path, record.category)
    if not files:
        raise ValueError(f"No matching files found in {record.content_path}")

    hint_author = ""
    if record.category == "audiobook":
        try:
            from app.audiofile import read_author
            hint_author = read_author(files)
            if hint_author:
                logger.debug(f"File metadata author for {record.name!r}: {hint_author!r}")
        except Exception as e:
            logger.debug(f"Could not read file metadata: {e}")

    is_comic_file = is_comic(files)
    result = resolve_metadata(
        record.name, record.category, hint_author=hint_author, is_comic=is_comic_file
    )
    record.metadata_confidence = result["confidence"]
    record.candidates_json = json.dumps([_strip_raw(c) for c in result["candidates"]])
    record.isbn = (result["match"] or {}).get("isbn", "") or None

    if current_app.config["SHADOW_MATCHER_ENABLED"]:
        # Countdown, not .delay(): dispatching immediately re-queries the
        # same Audible endpoint the real import above just hit, and Audible
        # rate-limits back-to-back requests for the same title (see
        # _search_audible's retry comment in app/metadata.py). Spacing it
        # out reduces how often the shadow-only call gets rate-limited.
        shadow_match_item.apply_async(
            args=[record.id, result, hint_author, is_comic_file],
            countdown=SHADOW_MATCH_DELAY_SECONDS,
        )

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

    linked = hardlink_files(files, target_dir, match["title"])
    if not linked:
        # Every target already existed (e.g. two different downloads
        # resolving to the same title) -- nothing was actually added to the
        # library. Marking this "imported" would look successful while
        # silently dropping the file.
        record.status = "failed"
        record.error_message = f"Target already exists, nothing new linked: {target_dir}"
        db.session.commit()
        return

    record.target_path = str(target_dir)
    record.status = "imported"
    db.session.commit()

    try:
        ABSClient().scan_library(record.category)
    except Exception as e:
        logger.warning(f"ABS scan failed (import still succeeded): {e}")


@celery.task(name="app.tasks.shadow_match_item")
def shadow_match_item(import_id: int, old_result: dict, hint_author: str, is_comic_file: bool):
    _run_shadow_match(import_id, old_result, hint_author, is_comic_file)


def _run_shadow_match(import_id: int, old_result: dict, hint_author: str, is_comic_file: bool):
    """Phase 4a: runs the new (still-unwired) resolver alongside the old
    one's already-decided result and records both for offline comparison.
    Dispatched fire-and-forget from _run_import so a slow API call or a bug
    in the new resolver can never delay or break the real import -- this
    function's own failures are caught and stored, never re-raised. See
    /root/.claude/plans/jolly-greeting-karp.md (Phase 4a)."""
    record = Import.query.get(import_id)
    if not record:
        return

    shadow = ShadowMatch(
        import_id=import_id,
        old_confidence=old_result["confidence"],
        old_match_json=json.dumps(_strip_raw(old_result["match"])),
    )
    try:
        new_result = resolve_metadata_v2(
            record.name, record.category, hint_author=hint_author, is_comic=is_comic_file
        )
        shadow.new_confidence = new_result["confidence"]
        shadow.new_match_json = json.dumps(_strip_raw(new_result["match"]))
        shadow.new_candidates_json = json.dumps([_strip_raw(c) for c in new_result["candidates"]])
        shadow.agrees = _matches_agree(old_result["match"], new_result["match"])
    except Exception as e:
        shadow.error = str(e)
        logger.exception(f"Shadow match failed for import {import_id}")

    db.session.add(shadow)
    db.session.commit()
