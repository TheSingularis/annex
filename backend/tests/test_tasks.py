from pathlib import Path

from app import db, tasks
from app.models import Import


def _make_import(**overrides):
    defaults = dict(name="Dune - Frank Herbert", category="ebook",
                     content_path="/tmp/x", status="importing")
    defaults.update(overrides)
    record = Import(**defaults)
    db.session.add(record)
    db.session.commit()
    return record


def test_run_import_persists_isbn_and_asin_from_match(db_app, monkeypatch):
    record = _make_import()
    monkeypatch.setattr(tasks, "discover_files", lambda path, category: [Path("/tmp/fake.epub")])
    monkeypatch.setattr(tasks, "is_comic", lambda files: False)
    monkeypatch.setattr(tasks, "resolve_metadata_v2", lambda *a, **k: {
        "confidence": 0.99,
        "match": {
            "author": "Frank Herbert", "title": "Dune",
            "isbn": "9780061122415", "asin": "B0192CTMYG",
        },
        "candidates": [],
    })
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    monkeypatch.setattr(tasks, "hardlink_files", lambda files, target_dir, title: [Path("/tmp/target/Dune.epub")])
    monkeypatch.setattr(tasks.ABSClient, "scan_library", lambda self, category: None)

    tasks._run_import(record)

    assert record.isbn == "9780061122415"
    assert record.asin == "B0192CTMYG"
    assert record.status == "imported"


def test_run_import_leaves_isbn_and_asin_null_when_absent_from_match(db_app, monkeypatch):
    record = _make_import()
    monkeypatch.setattr(tasks, "discover_files", lambda path, category: [Path("/tmp/fake.epub")])
    monkeypatch.setattr(tasks, "is_comic", lambda files: False)
    monkeypatch.setattr(tasks, "resolve_metadata_v2", lambda *a, **k: {
        "confidence": 0.99,
        "match": {"author": "Frank Herbert", "title": "Dune"},
        "candidates": [],
    })
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    monkeypatch.setattr(tasks, "hardlink_files", lambda files, target_dir, title: [Path("/tmp/target/Dune.epub")])
    monkeypatch.setattr(tasks.ABSClient, "scan_library", lambda self, category: None)

    tasks._run_import(record)

    assert record.isbn is None
    assert record.asin is None


# --- _finalize_import ---

def test_finalize_import_marks_failed_when_nothing_newly_linked(db_app, monkeypatch):
    # Regression: a target collision (hardlink_files returns an empty list --
    # every target already existed) used to still mark the record "imported",
    # looking successful while silently dropping the file.
    record = _make_import()
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    monkeypatch.setattr(tasks, "hardlink_files", lambda files, target_dir, title: [])

    tasks._finalize_import(
        record, {"author": "Frank Herbert", "title": "Dune"}, [Path("/tmp/fake.epub")]
    )

    assert record.status == "failed"
    assert "already exists" in record.error_message
    assert record.target_path is None
