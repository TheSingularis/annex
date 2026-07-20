import json
from pathlib import Path

from app import db, tasks
from app.models import Import, ShadowMatch


def _make_import(**overrides):
    defaults = dict(name="Dune - Frank Herbert", category="ebook",
                     content_path="/tmp/x", status="importing")
    defaults.update(overrides)
    record = Import(**defaults)
    db.session.add(record)
    db.session.commit()
    return record


# --- _run_shadow_match ---

def test_run_shadow_match_records_agreement(db_app, monkeypatch):
    record = _make_import()
    old_result = {"confidence": 0.9, "match": {"title": "Dune", "author": "Frank Herbert"}}
    new_result = {
        "confidence": 0.95,
        "match": {"title": "Dune", "author": "Frank Herbert"},
        "candidates": [{"title": "Dune", "author": "Frank Herbert"}],
    }
    monkeypatch.setattr(tasks, "resolve_metadata_v2", lambda *a, **k: new_result)

    tasks._run_shadow_match(record.id, old_result, "", False)

    shadow = ShadowMatch.query.filter_by(import_id=record.id).one()
    assert shadow.agrees is True
    assert shadow.error is None
    assert json.loads(shadow.new_match_json)["title"] == "Dune"


def test_run_shadow_match_records_disagreement(db_app, monkeypatch):
    record = _make_import()
    old_result = {"confidence": 0.9, "match": {"title": "Dune", "author": "Frank Herbert"}}
    new_result = {"confidence": 0.4, "match": None, "candidates": []}
    monkeypatch.setattr(tasks, "resolve_metadata_v2", lambda *a, **k: new_result)

    tasks._run_shadow_match(record.id, old_result, "", False)

    shadow = ShadowMatch.query.filter_by(import_id=record.id).one()
    assert shadow.agrees is False


def test_run_shadow_match_records_error_without_raising(db_app, monkeypatch):
    record = _make_import()
    old_result = {"confidence": 0.9, "match": {"title": "Dune", "author": "Frank Herbert"}}

    def boom(*a, **k):
        raise RuntimeError("api exploded")

    monkeypatch.setattr(tasks, "resolve_metadata_v2", boom)

    tasks._run_shadow_match(record.id, old_result, "", False)  # must not raise

    shadow = ShadowMatch.query.filter_by(import_id=record.id).one()
    assert "api exploded" in shadow.error
    assert shadow.new_confidence is None


def test_run_shadow_match_missing_import_is_a_noop(db_app):
    tasks._run_shadow_match(999999, {"confidence": 0.9, "match": None}, "", False)
    assert ShadowMatch.query.count() == 0


# --- _run_import shadow dispatch ---

def test_run_import_dispatches_shadow_task_when_enabled(db_app, monkeypatch):
    record = _make_import()
    monkeypatch.setattr(tasks, "discover_files", lambda path, category: [Path("/tmp/fake.epub")])
    monkeypatch.setattr(tasks, "is_comic", lambda files: False)
    monkeypatch.setattr(tasks, "resolve_metadata", lambda *a, **k: {
        "confidence": 0.2, "match": None, "candidates": []
    })
    calls = []
    monkeypatch.setattr(tasks.shadow_match_item, "delay", lambda *a, **k: calls.append(a))
    db_app.config["SHADOW_MATCHER_ENABLED"] = True

    tasks._run_import(record)

    assert len(calls) == 1
    assert calls[0][0] == record.id


def test_run_import_skips_shadow_dispatch_when_disabled(db_app, monkeypatch):
    record = _make_import()
    monkeypatch.setattr(tasks, "discover_files", lambda path, category: [Path("/tmp/fake.epub")])
    monkeypatch.setattr(tasks, "is_comic", lambda files: False)
    monkeypatch.setattr(tasks, "resolve_metadata", lambda *a, **k: {
        "confidence": 0.2, "match": None, "candidates": []
    })
    calls = []
    monkeypatch.setattr(tasks.shadow_match_item, "delay", lambda *a, **k: calls.append(a))
    db_app.config["SHADOW_MATCHER_ENABLED"] = False

    tasks._run_import(record)

    assert calls == []


def test_run_import_backfills_isbn_from_old_match(db_app, monkeypatch):
    record = _make_import()
    monkeypatch.setattr(tasks, "discover_files", lambda path, category: [Path("/tmp/fake.epub")])
    monkeypatch.setattr(tasks, "is_comic", lambda files: False)
    monkeypatch.setattr(tasks, "resolve_metadata", lambda *a, **k: {
        "confidence": 0.99,
        "match": {"author": "Frank Herbert", "title": "Dune", "isbn": "9780061122415"},
        "candidates": [],
    })
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    monkeypatch.setattr(tasks, "hardlink_files", lambda files, target_dir, title: None)
    monkeypatch.setattr(tasks.ABSClient, "scan_library", lambda self, category: None)
    monkeypatch.setattr(tasks.shadow_match_item, "delay", lambda *a, **k: None)
    db_app.config["SHADOW_MATCHER_ENABLED"] = False

    tasks._run_import(record)

    assert record.isbn == "9780061122415"
    assert record.status == "imported"
