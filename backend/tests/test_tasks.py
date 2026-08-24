import json
from pathlib import Path

from app import db, tasks
from app.ebook_convert import EbookConversionError
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


# --- _finalize_import ebook conversion ---

def test_finalize_import_ebook_native_epub_skips_conversion(db_app, monkeypatch):
    record = _make_import(category="ebook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    convert_calls = []
    monkeypatch.setattr(tasks, "convert_to_epub", lambda *a, **k: convert_calls.append(a) or Path("/tmp/should-not-be-used.epub"))
    linked_calls = []
    monkeypatch.setattr(
        tasks, "hardlink_files",
        lambda files, target_dir, title: linked_calls.append(files) or [Path("/tmp/target/Dune.epub")],
    )
    db_app.config["EBOOK_CONVERT_ENABLED"] = True

    tasks._finalize_import(
        record, {"author": "Frank Herbert", "title": "Dune"},
        [Path("/tmp/x/book.azw3"), Path("/tmp/x/book.epub")],
    )

    assert convert_calls == []
    assert linked_calls == [[Path("/tmp/x/book.epub")]]
    assert record.status == "imported"


def test_finalize_import_ebook_prefers_azw3_over_mobi_when_no_epub(db_app, monkeypatch):
    record = _make_import(category="ebook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    convert_calls = []

    def fake_convert(source, workdir):
        convert_calls.append(source)
        return workdir / "converted.epub"

    monkeypatch.setattr(tasks, "convert_to_epub", fake_convert)
    linked_calls = []
    monkeypatch.setattr(
        tasks, "hardlink_files",
        lambda files, target_dir, title: linked_calls.append(files) or [Path("/tmp/target/Dune.epub")],
    )
    db_app.config["EBOOK_CONVERT_ENABLED"] = True

    tasks._finalize_import(
        record, {"author": "Frank Herbert", "title": "Dune"},
        [Path("/tmp/x/book.mobi"), Path("/tmp/x/book.azw3")],
    )

    assert convert_calls == [Path("/tmp/x/book.azw3")]
    assert linked_calls[0][0].name == "converted.epub"
    assert record.status == "imported"


def test_finalize_import_ebook_mobi_only_converts(db_app, monkeypatch):
    record = _make_import(category="ebook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    convert_calls = []

    def fake_convert(source, workdir):
        convert_calls.append(source)
        return workdir / "converted.epub"

    monkeypatch.setattr(tasks, "convert_to_epub", fake_convert)
    monkeypatch.setattr(tasks, "hardlink_files", lambda files, target_dir, title: [Path("/tmp/target/Dune.epub")])
    db_app.config["EBOOK_CONVERT_ENABLED"] = True

    tasks._finalize_import(
        record, {"author": "Frank Herbert", "title": "Dune"}, [Path("/tmp/x/book.mobi")]
    )

    assert convert_calls == [Path("/tmp/x/book.mobi")]
    assert record.status == "imported"


def test_finalize_import_ebook_conversion_failure_marks_failed(db_app, monkeypatch):
    record = _make_import(category="ebook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))

    def boom(source, workdir):
        raise EbookConversionError("exit 1: corrupt file")

    monkeypatch.setattr(tasks, "convert_to_epub", boom)
    linked_calls = []
    monkeypatch.setattr(tasks, "hardlink_files", lambda *a, **k: linked_calls.append(1) or [])
    db_app.config["EBOOK_CONVERT_ENABLED"] = True

    tasks._finalize_import(
        record, {"author": "X", "title": "Y"}, [Path("/tmp/x/book.mobi")]
    )

    assert record.status == "failed"
    assert "corrupt file" in record.error_message
    assert record.target_path is None
    assert linked_calls == []  # never reaches hardlink_files


def test_finalize_import_ebook_pdf_alongside_azw3_pdf_still_linked(db_app, monkeypatch):
    record = _make_import(category="ebook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    monkeypatch.setattr(tasks, "convert_to_epub", lambda source, workdir: workdir / "converted.epub")
    linked_calls = []
    monkeypatch.setattr(
        tasks, "hardlink_files",
        lambda files, target_dir, title: linked_calls.append(files) or [Path("/tmp/target/x")],
    )
    db_app.config["EBOOK_CONVERT_ENABLED"] = True

    tasks._finalize_import(
        record, {"author": "X", "title": "Y"},
        [Path("/tmp/x/book.azw3"), Path("/tmp/x/notes.pdf")],
    )

    linked_files = linked_calls[0]
    assert linked_files[0].name == "converted.epub"
    assert Path("/tmp/x/notes.pdf") in linked_files


def test_finalize_import_audiobook_bypasses_conversion_entirely(db_app, monkeypatch):
    record = _make_import(category="audiobook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    select_calls = []
    monkeypatch.setattr(tasks, "select_ebook_source", lambda files: select_calls.append(1))
    monkeypatch.setattr(tasks, "hardlink_files", lambda *a, **k: [Path("/tmp/target/01.mp3")])
    db_app.config["EBOOK_CONVERT_ENABLED"] = True

    tasks._finalize_import(
        record, {"author": "X", "title": "Y"}, [Path("/tmp/x/01.mp3")]
    )

    assert select_calls == []
    assert record.status == "imported"


def test_finalize_import_ebook_convert_disabled_by_flag_hardlinks_everything(db_app, monkeypatch):
    record = _make_import(category="ebook")
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    convert_calls = []
    monkeypatch.setattr(tasks, "convert_to_epub", lambda *a, **k: convert_calls.append(1))
    linked_calls = []
    monkeypatch.setattr(
        tasks, "hardlink_files",
        lambda files, target_dir, title: linked_calls.append(files) or [Path("/tmp/target/book.azw3")],
    )
    db_app.config["EBOOK_CONVERT_ENABLED"] = False

    tasks._finalize_import(
        record, {"author": "X", "title": "Y"},
        [Path("/tmp/x/book.azw3"), Path("/tmp/x/book.mobi")],
    )

    assert convert_calls == []
    assert linked_calls == [[Path("/tmp/x/book.azw3"), Path("/tmp/x/book.mobi")]]
    assert record.status == "imported"


def test_finalize_import_persists_linked_files_json(db_app, monkeypatch):
    record = _make_import()
    monkeypatch.setattr(tasks, "build_target_dir", lambda **k: Path("/tmp/target"))
    monkeypatch.setattr(
        tasks, "hardlink_files",
        lambda files, target_dir, title: [Path("/tmp/target/Dune.epub")],
    )

    tasks._finalize_import(
        record, {"author": "Frank Herbert", "title": "Dune"}, [Path("/tmp/fake.epub")]
    )

    assert json.loads(record.linked_files_json) == ["/tmp/target/Dune.epub"]
